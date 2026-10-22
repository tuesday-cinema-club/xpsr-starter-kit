"""
Gate 02 / Gate 03 bridge: block an approved shot list in Blender.

Builds a grey-box set for each bible location, places one camera per shot
using the shot's real focal length and framing, then renders for every shot:

  shot_NN_grey.png   clay render for the director to approve framing
  shot_NN_depth.png  depth pass (near = white, far = black) for ControlNet

It also saves previs.blend so the Previs crew can open the scene and move the
cameras by hand, and previs.json with each camera's position and lens.

This is a deterministic script: same shots.json in, same pictures out.
Run it with Blender in the background (no window needed):

    blender -b --python-exit-code 1 -P pipelines/02-production/blender_previs.py -- \\
        --shots my-project/shots.json \\
        --bible templates/ember-and-oak-bible.json \\
        --out my-project/previs

Tested with Blender 4.2 LTS through 5.2 LTS.
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

WIDTH, HEIGHT = 1344, 768            # SDXL-native 16:9-ish bucket
SENSOR_W = 36.0                      # full-frame sensor width, mm
SENSOR_H = SENSOR_W * HEIGHT / WIDTH

# How much vertical space (metres) each framing fills at the subject.
FRAME_HEIGHT_M = {
    "Extreme Wide": 7.0,
    "Wide": 3.2,
    "Medium": 1.1,
    "Close Up": 0.45,
    "Extreme Close Up": 0.18,
}

LOCATION_SPACING = 40.0              # metres between sets so they never overlap


# --------------------------------------------------------------------------
# Scene helpers
# --------------------------------------------------------------------------

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, rgb, emission=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    if emission:
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = (1.0, 0.95, 0.85, 1.0)
                break
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def box(name, size, loc, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    obj.data.materials.append(mat)
    return obj


def cylinder(name, radius, depth, loc, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, rotation=rot, vertices=32)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def sphere(name, radius, loc, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=24, ring_count=12)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def person(name, base, mat, height=1.75):
    """Grey-box human: legs, torso, head and arms. Returns the head position."""
    x, y, z = base
    cylinder(f"{name}_legs", 0.16, height * 0.47, (x, y, z + height * 0.235), mat)
    cylinder(f"{name}_torso", 0.21, height * 0.33, (x, y, z + height * 0.635), mat)
    head = (x, y, z + height * 0.9)
    sphere(f"{name}_head", 0.12, head, mat)
    for side in (-1, 1):
        cylinder(f"{name}_arm_{side}", 0.05, height * 0.32, (x + side * 0.26, y, z + height * 0.62), mat)
    return Vector(head)


# --------------------------------------------------------------------------
# Sets. Each returns named anchor points the cameras aim at.
# --------------------------------------------------------------------------

def room_shell(ox, mats, depth=10.0, width=12.0, height=3.2, window_x=None):
    box("floor", (width, depth, 0.05), (ox, 0, -0.025), mats["floor"])
    box("back_wall", (width, 0.1, height), (ox, depth / 2, height / 2), mats["wall"])
    box("left_wall", (0.1, depth, height), (ox - width / 2, 0, height / 2), mats["wall"])
    # Window: an emissive panel on the right wall gives one soft side source.
    box("window_glow", (0.05, 2.0, 1.6), (ox + width / 2 - 0.05, 2.0, 1.7), mats["window"])
    bpy.ops.object.light_add(type="AREA", location=(ox + width / 2 - 0.4, 2.0, 1.8))
    light = bpy.context.active_object
    light.data.energy = 900
    light.data.size = 2.0
    light.rotation_euler = (0, math.radians(-90), 0)


def build_roastery(ox, mats):
    room_shell(ox, mats)
    box("roaster_stand", (1.2, 0.9, 0.8), (ox - 1.5, 2.6, 0.4), mats["prop"])
    cylinder("drum", 0.38, 1.0, (ox - 1.5, 2.6, 1.2), mats["prop"], rot=(0, math.radians(90), 0))
    cylinder("hopper", 0.22, 0.4, (ox - 1.7, 2.6, 1.75), mats["prop"])
    cylinder("cooling_tray", 0.45, 0.12, (ox - 0.4, 2.4, 0.95), mats["prop"])
    box("tray_stand", (0.8, 0.8, 0.9), (ox - 0.4, 2.4, 0.45), mats["prop"])
    box("pallet", (1.2, 1.0, 0.15), (ox + 2.0, 3.8, 0.075), mats["prop"])
    for i, (dx, dz) in enumerate([(-0.3, 0.35), (0.3, 0.35), (0.0, 0.75)]):
        box(f"sack_{i}", (0.55, 0.85, 0.4), (ox + 2.0 + dx, 3.8, dz), mats["sack"])
    box("chalkboard", (1.4, 0.04, 0.9), (ox, 4.93, 1.7), mats["dark"])
    box("work_table", (1.4, 0.7, 0.9), (ox + 0.9, 1.6, 0.45), mats["prop"])
    box("coffee_bag", (0.16, 0.09, 0.26), (ox + 0.9, 1.5, 1.03), mats["sack"])
    roaster_head = person("roaster", (ox - 0.4, 1.7, 0), mats["person"])
    regular_head = person("regular", (ox + 1.8, 0.4, 0), mats["person_b"], height=1.7)
    return {
        "center": Vector((ox, 2.0, 1.3)),
        "roaster": roaster_head,
        "regular": regular_head,
        "detail": Vector((ox + 0.9, 1.5, 1.05)),
    }


def build_new_shop(ox, mats):
    room_shell(ox, mats)
    box("counter", (3.2, 0.7, 1.0), (ox, 2.2, 0.5), mats["prop"])
    box("espresso_machine", (0.7, 0.5, 0.45), (ox - 0.8, 2.3, 1.225), mats["dark"])
    box("grinder", (0.2, 0.25, 0.45), (ox - 0.2, 2.3, 1.225), mats["dark"])
    box("coffee_bag", (0.16, 0.09, 0.26), (ox + 0.5, 2.0, 1.13), mats["sack"])
    box("menu_board", (1.6, 0.04, 0.8), (ox, 4.93, 2.0), mats["dark"])
    box("window_sign", (1.6, 0.03, 0.5), (ox + 3.0, 4.9, 1.6), mats["window"])
    roaster_head = person("roaster", (ox - 0.2, 2.9, 0), mats["person"])
    regular_head = person("regular", (ox + 1.3, 1.3, 0), mats["person_b"], height=1.7)
    return {
        "center": Vector((ox, 2.0, 1.3)),
        "roaster": roaster_head,
        "regular": regular_head,
        "detail": Vector((ox + 0.5, 2.0, 1.13)),
    }


def build_generic(ox, mats):
    """Fallback for locations this script has no hand-made set for."""
    room_shell(ox, mats)
    box("table", (2.0, 1.0, 0.9), (ox, 2.0, 0.45), mats["prop"])
    a = person("subject_a", (ox - 0.6, 2.8, 0), mats["person"])
    b = person("subject_b", (ox + 0.8, 1.0, 0), mats["person_b"], height=1.7)
    return {"center": Vector((ox, 2.0, 1.3)), "subject_a": a, "subject_b": b,
            "detail": Vector((ox, 2.0, 0.95))}


def car(name, base, mats, yaw=0.0):
    """Grey-box sedan facing +Y. Returns the centre of the hood."""
    x, y, z = base
    parts = [box(f"{name}_body", (1.8, 4.4, 0.7), (x, y, z + 0.6), mats["prop"]),
             box(f"{name}_cabin", (1.6, 2.2, 0.6), (x, y - 0.3, z + 1.25), mats["person_b"])]
    for dx in (-0.9, 0.9):
        for dy in (-1.4, 1.4):
            parts.append(cylinder(f"{name}_wheel", 0.33, 0.25, (x + dx, y + dy, z + 0.33), mats["dark"],
                                  rot=(0, math.radians(90), 0)))
    for p_ in parts:
        p_.rotation_euler.z += yaw
    return Vector((x, y + 1.6, z + 1.0))


def sun(ox, strength=2.0):
    bpy.ops.object.light_add(type="SUN", location=(ox, -10, 20))
    light = bpy.context.active_object
    light.data.energy = strength
    light.rotation_euler = (math.radians(50), 0, math.radians(30))


def build_vineyard_road(ox, mats):
    box("ground", (80, 80, 0.05), (ox, 20, -0.025), mats["floor"])
    box("road", (4.0, 80, 0.02), (ox, 20, 0.01), mats["dark"])
    for side in (-1, 1):
        for i in range(6):
            x = ox + side * (4.0 + i * 1.8)
            box(f"vine_row_{side}_{i}", (0.45, 60, 1.3), (x, 25, 0.65), mats["sack"])
    for i, (dx, r) in enumerate([(-25, 14), (5, 18), (30, 12)]):
        sphere(f"hill_{i}", r, (ox + dx, 60, -r * 0.55), mats["wall"])
    sphere("balloon", 2.2, (ox + 7, 40, 14), mats["person"])
    box("balloon_basket", (0.8, 0.8, 0.6), (ox + 7, 40, 11.2), mats["dark"])
    hood = car("sedan", (ox, 4.0, 0), mats)
    driver_head = person("driver", (ox + 1.6, 3.2, 0), mats["person_b"], height=1.7)
    sun(ox)
    return {"center": Vector((ox, 4.0, 1.0)), "driver": driver_head, "detail": hood}


def build_wash_tunnel(ox, mats):
    box("floor", (12, 16, 0.05), (ox, 4, -0.025), mats["floor"])
    for side in (-1, 1):
        box(f"tunnel_wall_{side}", (0.2, 12, 3.6), (ox + side * 3.2, 7, 1.8), mats["wall"])
        box(f"arch_pillar_{side}", (0.3, 0.3, 3.4), (ox + side * 2.6, 2.0, 1.7), mats["prop"])
        cylinder(f"side_brush_{side}", 0.55, 2.4, (ox + side * 1.9, 6.5, 1.3), mats["sack"])
    box("arch_beam", (5.5, 0.3, 0.3), (ox, 2.0, 3.4), mats["prop"])
    cylinder("top_brush", 0.5, 3.2, (ox, 8.5, 2.3), mats["sack"], rot=(0, math.radians(90), 0))
    box("tunnel_roof", (6.6, 12, 0.2), (ox, 7, 3.7), mats["wall"])
    hood = car("sedan", (ox, 3.4, 0), mats)          # nosing out under the arch
    box("podium", (0.6, 0.5, 1.1), (ox - 2.5, 0.2, 0.55), mats["prop"])
    attendant_head = person("attendant", (ox + 1.35, 2.2, 0), mats["person"])
    cylinder("flute", 0.04, 0.25, (ox + 1.1, 1.95, 1.25), mats["window"])
    driver_head = person("driver", (ox - 1.5, 1.0, 0), mats["person_b"], height=1.7)
    bpy.ops.object.light_add(type="AREA", location=(ox, 3, 3.4))
    bpy.context.active_object.data.energy = 350
    bpy.context.active_object.data.size = 4
    sun(ox, 1.5)
    return {"center": Vector((ox, 4.0, 1.2)), "attendant": attendant_head, "driver": driver_head,
            "detail": Vector((ox + 1.1, 1.95, 1.3))}


SET_BUILDERS = {"roastery": build_roastery, "new_shop": build_new_shop,
                "vineyard_road": build_vineyard_road, "wash_tunnel": build_wash_tunnel}


# --------------------------------------------------------------------------
# Cameras and rendering
# --------------------------------------------------------------------------

def aim_point(shot, anchors):
    """Where the lens points: the detail prop for close shots, the first
    character's head for medium shots, the middle of the cast for wides."""
    framing = shot["framing"]
    chars = [anchors[c] for c in shot["characters"] if c in anchors]
    if framing in ("Close Up", "Extreme Close Up"):
        return anchors["detail"]
    if framing == "Medium" and chars:
        return chars[0] - Vector((0, 0, 0.35))
    if chars:
        mid = sum(chars, Vector()) / len(chars)
        return Vector((mid.x, mid.y, 1.2))
    return anchors["center"]


def place_camera(shot, anchors, index):
    target = aim_point(shot, anchors)
    lens = shot["lens_mm"]
    distance = FRAME_HEIGHT_M[shot["framing"]] * lens / SENSOR_H
    yaw = math.radians((-1) ** index * 12)            # alternate sides of the line
    height = target.z + (0.25 if shot["framing"] in ("Wide", "Extreme Wide") else 0.05)
    pos = Vector((target.x + math.sin(yaw) * distance, target.y - math.cos(yaw) * distance, height))
    bpy.ops.object.camera_add(location=pos)
    cam = bpy.context.active_object
    cam.name = f"CAM_shot_{shot['shot_number']:02d}"
    cam.data.lens = lens
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = SENSOR_W
    cam.data.clip_start = 0.05
    direction = target - pos
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return cam, distance, target


def depth_material(near, far):
    mat = bpy.data.materials.get("DEPTH") or bpy.data.materials.new("DEPTH")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    cam = nt.nodes.new("ShaderNodeCameraData")
    rng = nt.nodes.new("ShaderNodeMapRange")
    emit = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    rng.inputs["From Min"].default_value = near
    rng.inputs["From Max"].default_value = far
    rng.inputs["To Min"].default_value = 1.0
    rng.inputs["To Max"].default_value = 0.0
    rng.clamp = True
    nt.links.new(cam.outputs["View Distance"], rng.inputs["Value"])
    nt.links.new(rng.outputs["Result"], emit.inputs["Strength"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def configure_render(scene):
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = WIDTH
    scene.render.resolution_y = HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = backend
            except TypeError:
                continue
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type != "CPU"]
            if gpus:
                for d in prefs.devices:
                    d.use = True
                scene.cycles.device = "GPU"
                print(f"[previs] rendering on GPU via {backend}")
                return
        print("[previs] no GPU backend found; rendering on CPU")
    except Exception as exc:  # pragma: no cover - depends on the machine
        print(f"[previs] GPU setup skipped ({exc}); rendering on CPU")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Grey-box previs and depth passes from shots.json")
    p.add_argument("--shots", required=True)
    p.add_argument("--bible", required=True)
    p.add_argument("--out", required=True, help="Output folder for PNGs, previs.blend and previs.json")
    p.add_argument("--samples", type=int, default=32)
    args = p.parse_args(argv)

    with open(args.shots, encoding="utf-8") as f:
        shots = json.load(f)
    with open(args.bible, encoding="utf-8") as f:
        bible = json.load(f)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    clear_scene()
    scene = bpy.context.scene
    configure_render(scene)
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.35, 0.35, 0.37, 1.0)
    bg.inputs["Strength"].default_value = 0.6

    mats = {
        "floor": material("floor", (0.30, 0.30, 0.30)),
        "wall": material("wall", (0.55, 0.55, 0.55)),
        "prop": material("prop", (0.62, 0.62, 0.62)),
        "dark": material("dark", (0.18, 0.18, 0.18)),
        "sack": material("sack", (0.70, 0.70, 0.68)),
        "person": material("person", (0.82, 0.82, 0.82)),
        "person_b": material("person_b", (0.72, 0.74, 0.78)),
        "window": material("window", (1.0, 1.0, 1.0), emission=4.0),
    }

    anchors_by_loc = {}
    for i, loc in enumerate(bible["locations"]):
        builder = SET_BUILDERS.get(loc["id"], build_generic)
        anchors_by_loc[loc["id"]] = builder(i * LOCATION_SPACING, mats)

    records = []
    for i, shot in enumerate(shots["shots"]):
        anchors = anchors_by_loc.get(shot["location_id"]) or next(iter(anchors_by_loc.values()))
        cam, distance, target = place_camera(shot, anchors, i)
        scene.camera = cam
        n = shot["shot_number"]

        scene.cycles.samples = args.samples
        bpy.context.view_layer.material_override = None
        scene.render.filepath = os.path.join(out, f"shot_{n:02d}_grey.png")
        bpy.ops.render.render(write_still=True)

        scene.cycles.samples = 8
        bpy.context.view_layer.material_override = depth_material(max(0.05, distance * 0.5), distance + 4.0)
        scene.render.filepath = os.path.join(out, f"shot_{n:02d}_depth.png")
        bpy.ops.render.render(write_still=True)
        bpy.context.view_layer.material_override = None

        records.append({
            "shot_number": n,
            "camera": cam.name,
            "lens_mm": shot["lens_mm"],
            "framing": shot["framing"],
            "camera_move": shot["camera_move"],
            "distance_m": round(distance, 2),
            "position_m": [round(v, 3) for v in cam.location],
            "target_m": [round(v, 3) for v in target],
            "grey": f"shot_{n:02d}_grey.png",
            "depth": f"shot_{n:02d}_depth.png",
        })
        print(f"[previs] shot {n}: {shot['framing']} {shot['lens_mm']}mm at {distance:.2f} m")

    with open(os.path.join(out, "previs.json"), "w", encoding="utf-8") as f:
        json.dump({"blender": bpy.app.version_string, "resolution": [WIDTH, HEIGHT], "shots": records}, f, indent=2)
        f.write("\n")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "previs.blend"))
    print(f"[previs] wrote {len(records)} shots to {out}")


if __name__ == "__main__":
    main()
