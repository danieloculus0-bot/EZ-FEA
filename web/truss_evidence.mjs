/** Browser read-only evidence guard. It does not run finite elements. */
export const SCHEMA="ezfea.truss_browser_evidence.v1";

export function validateTrussEvidence(value){
  if(!value||value.schema!==SCHEMA)throw new Error("Unrecognized truss evidence");
  if(value.status!=="archived_real_solver_result_not_live_browser_solve")
    throw new Error("This is not archived native solver evidence");
  const g=value.geometry,n=value.native;
  if(!g||!n||g.type!=="fused_one_solid"||g.member_count!==10||
     !Array.isArray(g.members)||g.members.length!==10||
     g.span_mm!==600||g.rise_mm!==180)
    throw new Error("Warren truss CAD specification does not match the case");
  for(const member of g.members){
    if(!member||typeof member.id!=="string"||!["chord","web"].includes(member.kind)||
       ![18,24].includes(member.square_side_mm)||
       !Array.isArray(member.start)||!Array.isArray(member.end)||
       member.start.length!==3||member.end.length!==3||
       ![...member.start,...member.end].every(Number.isFinite))
       throw new Error("Truss member geometry incomplete or invalid");
  }
  if(!g.support_pads||g.support_pads.left?.axes!=="XYZ"||
     g.support_pads.right?.axes!=="YZ"||
     JSON.stringify(g.load_pad?.force_n)!==JSON.stringify([0,-1000,0]))
    throw new Error("Truss case must retain the real fixed/slide and load conditions");
  if(n.mesh_type!=="C3D10"||!Number.isInteger(n.elements)||n.elements<100||
     !Number.isFinite(n.mesh_target_mm)||n.mesh_target_mm<=0||
     !Number.isFinite(n.max_displacement_mm)||n.max_displacement_mm<=0||
     !Number.isFinite(n.peak_von_mises_mpa)||n.peak_von_mises_mpa<=0||
     n.force_balance_check!=="pass"||n.moment_balance_check!=="pass")
    throw new Error("Measured native 3D solver outputs are not complete or balanced");
  if(!/^https:\/\/github\.com\/danieloculus0-bot\/EZ-FEA\/actions\/runs\/\d+$/.test(value.source_run||""))
    throw new Error("Real solver provenance link unavailable");
  if(!Array.isArray(value.limits)||value.limits.length<3)
    throw new Error("Engineering limitations were not published");
  if(g.stl_sha256!==undefined &&
     !/^[a-f0-9]{64}$/.test(g.stl_sha256))
    throw new Error("Original CAD tessellation is missing an SHA256 digest");
  return value;
}
