# Reviewed Joint Matrix to real native two-part contact

This is the **first explicit mechanical assembly integration**. It links the STEP mate scanner, Joint Matrix and native CalculiX C3D10 contact experiment, without treating geometric proximity or a “welded” label as a real joint.

## What now connects

1. Scan a real STEP containing **two independent solids** with `ezfea.assembly_mates`; normalize to mm and record the source STEP SHA256, independent component IDs and candidate coincident planar CAD faces.
2. Transfer that graph into `ezfea.joint_matrix.matrix_from_graph`, preserving exact source hash.
3. Inspect the single candidate and explicitly select **Contact only** with `joint_confirmation=explicit_user_choice` and `mechanical_model=experimental_separable_contact`. An unassigned joint or a merely labelled weld, bolt or pin does **not** map into a solver.
4. The new `ezfea.assembly_physics.reviewed_contact_plan` rejects changed STEP files, missing/unstable face IDs, unknown material interfaces, ungrounded upper pads, more than two components, or ambiguous/unreviewed physics.
5. The limited native STEP backend reopens the **same** CAD file, verifies that the selected component and face IDs match the actual two stacked solids, meshes separate C3D10 volumes, and uses a **real frictionless contact pair**, not a fake tie. It solves compression, a no-contact control, and opening, then checks support reactions.

This is a bounded extension of the existing [separate-solid STEP contact verification](PRESSURE_CONTACT.md), not a complete multi-part design tool.

## Run

```bash
python -m ezfea.assembly_mates two_parts.step --out candidate_graph.json
```

Review the candidate, export a real Joint Matrix JSON containing the source hash and the explicit physically supported `Contact only` and `experimental_separable_contact` choices. The scanner itself never supplies the approval.

```bash
python -m ezfea.assembly_physics two_parts.step reviewed_matrix.json --out runs/reviewed_contact --mesh 7
```

Native Gmsh, CalculiX, correct STEP geometry and a valid interface are required. The run archives the original STEP, reviewed plan, C3D10 solver input, native outputs and measured support reactions.

[End-to-end test workflow](https://github.com/danieloculus0-bot/EZ-FEA/actions/workflows/reviewed-assembly-contact.yml) constructs a controlled two-brick STEP specimen, **simulates explicit selection in the test harness** and uses the resulting user-choice fields to exercise the real solver. No real human checked that artificial fixture.

## Current bounds

- Exactly two touching, coaxial, axis-aligned box-type solids with the prescribed vertical fixture/load geometry.
- One reviewed coincident planar contact, with zero shared volume mesh nodes and frictionless normal-only force transfer.
- Prescribed axial compression and opening; no free-form assembly loads, user-defined supports, surface friction or tangential stiffness.
- There is **no automatic weld, bolt, pinned-joint or arbitrary bonded connection model**. Joint labels alone never add mechanical constraints.
- Contact reaction passing is **not** verified stress distribution, pressure convergence, bolt pretension, material failure, design release or building-code approval.

Next: general CAD-surface selection without hard-coded planes, supported joint library one mechanism at a time, genuine assembly loading and restraint definitions, force/moment audits by interface, mesh/contact convergence, and feeding independent native results into BEAN's engineering curriculum as external measured evidence.
