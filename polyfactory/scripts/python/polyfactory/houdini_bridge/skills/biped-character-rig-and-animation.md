---
name: biped-character-rig-and-animation
description: Native Houdini 21 pipeline for rigging, posing, and animating bipedal characters (Otto rig, Autorig Builder, pose libraries, Mixamo/CMU retargeting) — for decorative game characters.
when_to_use: When starting on bipedal/humanoid characters for the game — choosing a rig, skinning a custom character mesh, building a pose library, or bringing in animation (Mixamo or other mocap) to pose/animate decorative characters. Reach for this before researching rigging from scratch.
tags: kinefx, apex, rig, biped, character, animation, mixamo, mocap, pose, retarget, skinning, otto
---

Goal: get a skinned, posable, animatable biped in Houdini 21 using **native** tools (no third-party rig). Verified against Houdini 21.0.631.

## 1. The rig — use Otto (native, skinned biped)
`testgeometry_otto` SOP ships with H21: production-quality male, real skin + muscles + bones, full APEX rig, ML skin deform, built-in **Full-Body IK** and **ragdoll** configs. This is the correct skinned humanoid — NOT Electra (Electra is a robot with disconnected limbs, no skin deformation; do not use it for skinning).

Otto output modes (param `Output`):
- **APEX Scene** → select node, click **Animate** on the left viewport toolbar. An `apex::sceneanimate` SOP is auto-placed and you enter the animate state — immediately posable. Easiest start.
- **APEX Character** → full character + rig you add to a scene: `apex::sceneaddcharacter` (names it) → `apex::sceneanimate`. This is the reusable form.
- **Level of Detail → Proxy** + turn OFF muscle/organ/sim toggles for a LIGHT rig (game/decorative use). Full Otto with muscles + ML is heavy.
- Otto ships with its own sample **animation clips** (Animation Clip Parms on the node).
- `Configure FBIK` / `Configure Ragdoll` toggles add those tools to the animate state.

## 2. Rigging YOUR OWN character meshes
- **Autorig Builder** (`apex::autorigbuilder`, new in H21): Pack Character SOP → Autorig Builder SOP → drag-and-drop biped components in viewport (root, spine, limb, hand, foot, neck, scapula, ulna, twist). Auto-maps joints, mirrors L/R.
- **Rig template** system: save a built rig config and transfer it to other characters with different proportions/naming. Build the biped rig once, reuse across all decorative characters.
- Borrow Otto's anatomy onto a custom mesh: Topo Transfer SOP + the "Test Geometry: Otto Muscle Transfer" recipe.
- Skinning a custom mesh: `Joint Capture Biharmonic` SOP (rest geo + capture pose + animated pose) gets ~80% of weights procedurally.

## 3. Pose library (native — this is the "pose library" answer)
- **Animation Catalog** (in the Animate state): save / manage / apply both **single-frame poses** AND full animation clips, reusable across scenes. This IS the native pose library.
- **Rig Pose** / **Rig Stash Pose** / **Rig Mirror Pose** SOPs: author a pose, stash as point attr, mirror L↔R procedurally.
- **Pose Blend** rig component: blend between stored poses (good for stylized pose presets).
- Build your own pose set by mining clips: `kinefx::motionclipextractkeyposes` pulls key poses out of any animation clip into your library. (Full MotionClip family present: blend, cycle, retime, sequence.)

## 4. Animation sources
- **Mixamo** (the user's default, fine to use): download FBX, import, retarget onto Otto/custom skeleton.
- **CMU Graphics Lab Mocap DB** (free, ~2600 clips, http://mocap.cs.cmu.edu/): big non-Mixamo library. Import BVH/ASF-AMC via **Mocap Import SOP** (`kinefx::mocapimport`), then retarget.
- Other free: Truebones, Rokoko free library, ActorCore samples, LAFAN1/100STYLE BVH datasets — all via Mocap Import (BVH/Acclaim/Motion Analysis).
- Live mocap: **Mocap Stream SOP** supports Rokoko, OptiTrack, Xsens, Vicon, Perception Neuron, Faceware.

## 5. Retargeting workflow (any source → Otto/custom)
KineFX import (source: mocap/animated) + KineFX import (target: your static skeleton) → **Rig Match Pose** SOP (conform poses, store rest) → retarget chain. See docs/houdini/character/kinefx/retargeting.html.
- **Trap:** Mixamo (and many mocap) clips need a **T-pose (or near it) on frame 1** of the source, or the retargeter accumulates offsets and the result is garbage.

## Done when
A posed/animated Otto (or custom rigged biped) plays back with correct skin deformation in the viewport, driven from a pose in the Animation Catalog or a retargeted clip — and the rig config is saved as a reusable template for the next character.

## Canonical docs
- Otto: nodes/sop/testgeometry_otto (local help server)
- Autorig Builder: character/kinefx/autorigbuilder.html
- Posing / Animation Catalog: character/kinefx/posing.html
- Mocap import: character/kinefx/motioncapture.html
- Retargeting: character/kinefx/retargeting.html
