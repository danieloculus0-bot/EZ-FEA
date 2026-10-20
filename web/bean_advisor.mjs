/**
 * Browser-side BEAN engineering checks for the EZ-FEA demo.
 *
 * A transparent, deterministic advisor over *real* beam results, modeled
 * boundary-condition declarations, and reference CalculiX runs.
 * NOT an invocation of BEAN Core, not a generative AI, and not an FEA solver.
 */
const finitePositive = (v) => Number.isFinite(v) && v > 0;
const readable = (v, digits=3) => Number.isFinite(v) ? Number(v.toPrecision(digits)).toLocaleString("en-US") : "unavailable";

export function reviewBeam(params, result=null) {
  const {length:L,width:b,height:h,force:P} = params;
  if (![L,b,h,P].every(Number.isFinite) || ![L,b,h].every(finitePositive)) {
    return {
      headline:"Check the beam inputs",
      advice:"Length, width, height and force must be valid numbers. No engineering conclusion is possible yet.",
      kind:"needs-input"
    };
  }
  const aspect=L/h;
  if (result === null) {
    const note = Math.abs(P) === 0
      ? "With zero applied force, a zero movement result won't tell us much about stiffness."
      : aspect < 8
        ? "This is a relatively deep beam (span/height " + readable(aspect) + "). Shear deformation may matter; the demo's Euler–Bernoulli model neglects it."
        : "Span/height is " + readable(aspect) + ". Run the real beam calculation and I'll check stress usage, displacement and numerical agreement.";
    return {headline:"BEAN is reading the setup",advice:note,kind:"setup"};
  }
  if (!Number.isFinite(result.deflection_mm) ||
      !Number.isFinite(result.peak_bending_stress_mpa) ||
      !Number.isFinite(result.verification_relative_error)) {
    return {headline:"Incomplete numerical result",advice:"The solver output is missing quantities needed for an engineering review.",kind:"needs-input"};
  }
  if (result.verification_relative_error > 0.01) {
    return {
      headline:"Numerical cross-check needs review",
      advice:"The beam FE movement differs from its independent closed-form reference by " +
        readable(100*result.verification_relative_error) + "%. Review the solver before interpreting strength.",
      kind:"review"
    };
  }
  if (Math.abs(P)===0) {
    return {headline:"No external force applied",
      advice:"The beam solves to zero movement and stress. Apply a nonzero test load to evaluate stiffness.",
      kind:"setup"};
  }
  const stressUsage = result.nominal_yield_mpa > 0
    ? 100*result.peak_bending_stress_mpa/result.nominal_yield_mpa
    : NaN;
  const deflectionRatio = result.deflection_mm/L;
  const notes = [];
  let headline="Initial beam check";
  let kind="reference";
  if (stressUsage>=100) {
    headline="Nominal yield exceeded";
    kind="review";
    notes.push("Calculated bending stress reaches " + readable(stressUsage) +
      "% of the selected material's nominal yield. This simple linear model cannot predict post-yield behavior.");
  } else if (stressUsage>=75) {
    headline="High nominal stress usage";
    kind="review";
    notes.push("The idealized beam uses " + readable(stressUsage) +
      "% of nominal yield. Check actual material data and real mounting before making a decision.");
  } else {
    notes.push("Calculated bending stress is " + readable(stressUsage) +
      "% of nominal yield in this beam-only model.");
  }
  notes.push("Tip displacement is " + readable(result.deflection_mm) +
    " mm (" + readable(100*deflectionRatio) +
    "% of span). A permissible deflection limit has not been specified.");
  if (aspect < 8) {
    kind="review";
    notes.push("Span/height " + readable(aspect) +
      " is short enough that neglected shear deflection can matter.");
  } else if (aspect > 25) {
    notes.push("The member is slender; check stability and buckling separately.");
  }
  notes.push("The FE tip result agrees with the analytical cantilever reference to " +
    readable(100*result.verification_relative_error,2) + "% difference.");
  return {headline, advice:notes.join(" "),kind};
}

export function reviewCad({filename="",fixed=null,load=null}={}) {
  if (!fixed && !load) {
    return {headline:"CAD preview, not a structural solve",
      advice:"I can help organize the load case. Mark where the part is supported and where the force enters. These points are not yet physical joints or CalculiX face IDs.",
      kind:"setup"};
  }
  if (!fixed || !load) {
    return {headline:"One boundary-condition location marked",
      advice:(fixed ? "Connection" : "Force") +
        " is marked. Add the other reference location next. BEAN cannot infer a bolt, hinge or clamp from a point.",
      kind:"setup"};
  }
  const p=fixed,q=load;
  const span=Math.hypot(p.x-q.x,p.y-q.y,p.z-q.z);
  return {headline:"Two reference locations identified",
    advice:"The marks are " + readable(span) +
      " model-coordinate units apart in " + (filename||"this preview") +
      ". They are not solver-ready restraints/loads: actual units, load direction, connected faces and joint behavior still need confirmation.",
    kind:"review"};
}

export function reviewFrameStudies(studies) {
  if (!Array.isArray(studies) || studies.length!==3) throw new TypeError("Expected three recorded frame results.");
  for (const row of studies) {
    if (!row?.key || !finitePositive(row.max_displacement_mm) ||
        !finitePositive(row.max_von_mises_mpa) ||
        !Number.isFinite(row.force_balance_relative_error) ||
        row.force_balance_relative_error > .01) {
      throw new TypeError("Incomplete frame study evidence.");
    }
  }
  const rectangle=studies.find(row=>row.key==="02_rectangle_racking");
  const braced=studies.find(row=>row.key==="03_braced_racking");
  if (!rectangle||!braced)throw new TypeError("Missing comparable frame specimens.");
  return {ratio:rectangle.max_displacement_mm/braced.max_displacement_mm,
    bracedStiffer:braced.max_displacement_mm < rectangle.max_displacement_mm};
}
