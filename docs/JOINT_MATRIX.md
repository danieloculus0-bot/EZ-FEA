# EZ-FEA — Assembly Mate Detection and Joint Matrix

Last development verification: October 20, 2026.

This is the first native **geometry-to-candidate-joint graph** and **spreadsheet editing** milestone. It is not automatic classification of mechanical connection physics.

## Workflow

1. Import an assembly STEP file containing **separate solids** into the Gmsh/OpenCascade detector. The scanner inspects per-component planar CAD face bounds and conservative opposing-face overlaps, rather than fusing the parts.
2. Choose a grounded component. EZ-FEA builds a topological graph of candidate contacts, recording which components are connected to ground, branches, redundant links/cycles and detached parts.
3. Inspect the candidate joints in the **Joint Matrix**. Each joint has a stable J-### ID, two component IDs, paired CAD face IDs, a detected geometry description, joint classification and a solver model field.
4. Choose the **Joint type** from the dropdown (Unassigned, Welded, Bolted, Pinned, Bearing, Bonded, Sliding, Contact only), then **drag the little green square downward** to fill a range. You can also Shift-click the target row and use **Fill selection down**, paste a column of newline-separated types, undo/redo and export CSV/JSON.
5. Classifications remain distinct from actual mechanical constraints: changing twenty joints to *Welded* does **not** automatically create mesh ties, weld stiffness, contact pairs, bolt pretension, or forces. The `mechanical_model` remains `unassigned` pending explicit physical definition and native verification.

The development workbench is **[Joint Matrix](https://danieloculus0-bot.github.io/EZ-FEA/joint-matrix.html)**. The main EZ-FEA browser demo remains unchanged; this is a separate feature workspace with sample rows (identified as sample data), plus JSON import from the genuine native detector.

## Real STEP experiment

[**Successful native STEP mate detection and spreadsheet test suite**](https://github.com/danieloculus0-bot/EZ-FEA/actions/runs/39510144813)

The same two independent real STEP steel cubes used in the pressure/contact work were inspected with Gmsh/OpenCascade. One component was grounded, and the scanner found one candidate interface: **two coincident, opposing planar faces overlapping 100.000 mm²**. It reported the first joint as **unassigned**, **not reviewed**, and **no mechanical model**. This is desired: the geometry does not reveal whether that interface should be welded, bolted, bonded or merely in contact.

The native CI artifact contains:

- `two_distinct_parts.step`: source geometry with separate bodies.
- `mate_graph.json`: grounded component graph and CAD evidence.
- `joint_matrix.json`: ready to import into the browser editor.
- `joint_matrix.csv`: editable spreadsheet export.
- `MATE_DETECTION_REPORT.md`: native proof and limitations.

### Run scanner locally

With Gmsh Python installed:

```bash
python -m ezfea.assembly_mates path/to/assembly.step --ground 1 --out mates.json
```

The `--ground` argument uses the current Gmsh component tag. Omit it to ground the first solid. Open **Joint Matrix → Import scanned joints JSON** and select `mates.json`. The native Python `ezfea.joint_matrix` layer offers equivalent validated `fill_down`, `paste_column` and `export_csv` operations for later application integration.

## Evidence and limits

At this stage, mate detection supports **coincident axis-aligned planar faces** with finite overlapping bounding rectangles and opposing orientations. Bounding rectangles are geometric evidence, not precise face intersection area for irregular profiles. The scanner cannot yet reliably infer coincident cylinders, fastener-hole patterns, concentric bearings, fillet welds, clearance, press fits, grounded kinematic DOFs or joint stiffness. A candidate graph is **not** a solved assembly, and reachability from grounded geometry is **not** a stability proof.

Next development: true surface overlap, concentric-cylindrical / hole-pattern candidate detectors, physically meaningful constraint templates, multiple closed loops, per-joint parameter columns (weld size, fastener group, friction, bearing clearance), and converting **explicitly confirmed** joints to validated native contact/tie/connector models. A clicked `Welded` classification alone must never silently create a fixed boundary condition.

[Native separate-solid contact proof](PRESSURE_CONTACT.md) is already supported on a tightly controlled two-solid STEP specimen; general assembly joint solving is **not** yet released. No result may be used as a qualified engineering design.
