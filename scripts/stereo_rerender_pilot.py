"""Render a bounded, calibrated stereo preview from a TRELLIS GLB asset.

Run inside Blender on a Slurm compute node. The left camera is copied from an
existing renders_cond frame; the right camera is translated along its local X.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mesh_bounds():
    points = [obj.matrix_world @ Vector(corner)
              for obj in bpy.context.scene.objects if obj.type == "MESH"
              for corner in obj.bound_box]
    if not points:
        raise ValueError("GLB contains no mesh")
    return (Vector(tuple(min(point[i] for point in points) for i in range(3))),
            Vector(tuple(max(point[i] for point in points) for i in range(3))))


def normalize_scene():
    roots = [obj for obj in bpy.context.scene.objects if obj.parent is None]
    if len(roots) > 1:
        root = bpy.data.objects.new("StereoNormalizationRoot", None)
        bpy.context.scene.collection.objects.link(root)
        for obj in roots:
            obj.parent = root
    else:
        root = roots[0]
    lo, hi = mesh_bounds()
    scale = 1.0 / max(hi - lo)
    root.scale *= scale
    bpy.context.view_layer.update()
    lo, hi = mesh_bounds()
    offset = -(lo + hi) / 2.0
    root.matrix_world.translation += offset
    bpy.context.view_layer.update()
    return scale, list(offset)


def add_lighting():
    for name, kind, energy, location, size in (
        ("Key", "POINT", 1000, (4, 1, 6), None),
        ("Top", "AREA", 10000, (0, 0, 10), 100),
        ("Bottom", "AREA", 1000, (0, 0, -10), None),
    ):
        obj = bpy.data.objects.new(name, bpy.data.lights.new(name, kind))
        bpy.context.scene.collection.objects.link(obj)
        obj.data.energy = energy
        obj.location = location
        if size is not None:
            obj.scale = (size, size, size)


def compose_preview(paths, output, resolution):
    images = [bpy.data.images.load(path, check_existing=False) for path in paths]
    for img in images:
        img.scale(resolution, resolution)
    target = bpy.data.images.new("original_left_right", resolution * len(images), resolution, alpha=True)
    pixels = np.concatenate(
        [np.asarray(img.pixels[:], dtype=np.float32).reshape(resolution, resolution, 4)
         for img in images], axis=1)
    target.pixels.foreach_set(pixels.ravel())
    target.filepath_raw = output
    target.file_format = "PNG"
    target.save()


def main(args):
    started = time.monotonic()
    os.makedirs(args.output, exist_ok=True)
    with open(args.transforms, encoding="utf-8") as stream:
        source = json.load(stream)
    frame = source["frames"][args.frame]
    original = os.path.join(os.path.dirname(args.transforms), frame["file_path"])
    if not os.path.isfile(original):
        raise FileNotFoundError(original)
    source_asset_sha = sha256(args.asset)
    if source_asset_sha != args.sha256:
        raise ValueError(f"Asset hash mismatch: {source_asset_sha} != {args.sha256}")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=args.asset, merge_vertices=True, import_shading="NORMALS")
    scale, offset = normalize_scene()
    if abs(scale - source["scale"]) > 1e-4 or np.max(np.abs(np.array(offset) - source["offset"])) > 1e-4:
        raise ValueError("GLB normalization differs from recorded transforms")
    add_lighting()

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    cam = bpy.data.objects.new("StereoCamera", bpy.data.cameras.new("StereoCamera"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.sensor_width = cam.data.sensor_height = 32
    fov = float(frame["camera_angle_x"])
    cam.data.lens = 16 / math.tan(fov / 2)
    left = np.array(frame["transform_matrix"], dtype=np.float64)
    if not np.allclose(left[3], [0, 0, 0, 1]) or abs(np.linalg.det(left[:3, :3]) - 1) > 1e-3:
        raise ValueError("Source camera is not a proper rigid transform")
    right = left.copy()
    right[:3, 3] += args.baseline * left[:3, 0]
    fx = args.resolution / (2 * math.tan(fov / 2))
    camera_data = {}
    for name, matrix in (("left", left), ("right", right)):
        cam.matrix_world = Matrix(matrix.tolist())
        bpy.context.view_layer.update()
        output = os.path.join(args.output, f"{name}.png")
        scene.render.filepath = output
        t0 = time.monotonic()
        bpy.ops.render.render(write_still=True)
        camera_data[name] = {"image": output, "camera_to_world_blender": matrix.tolist(),
                             "render_seconds": time.monotonic() - t0}
    preview = os.path.join(args.output, "original_left_right.png")
    compose_preview([original, camera_data["left"]["image"], camera_data["right"]["image"]],
                    preview, args.resolution)
    receipt = {
        "schema": "cupid_stereo_rerender_pilot_v1",
        "dataset": args.dataset,
        "asset": args.asset,
        "asset_sha256": source_asset_sha,
        "transforms": args.transforms,
        "transforms_sha256": sha256(args.transforms),
        "source_frame": args.frame,
        "original_image": original,
        "original_image_sha256": sha256(original),
        "normalization_scale": scale,
        "normalization_offset": offset,
        "resolution": args.resolution,
        "samples": args.samples,
        "baseline_normalized_units": args.baseline,
        "camera_model": "Blender perspective, sensor width 32 mm, square pixels, no distortion",
        "K": [[fx, 0, args.resolution / 2], [0, fx, args.resolution / 2], [0, 0, 1]],
        "pair": camera_data,
        "preview": preview,
        "total_seconds": time.monotonic() - started,
        "scientific_claim": "PILOT_ONLY",
    }
    with open(os.path.join(args.output, "receipt.json"), "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
    print("STEREO_PILOT_RECEIPT " + json.dumps(receipt), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--transforms", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--frame", type=int, default=0)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--baseline", type=float, default=0.05)
    argv = sys.argv[sys.argv.index("--") + 1:]
    main(parser.parse_args(argv))
