# Tiger I late-production geometry pass 02

Target remains Tiger I, May 1944 type, steel road wheels and 40 mm turret roof.
Audit performed before mesh work, 2026-09-16. This pass corrects primary volumes;
it does not claim a complete production-detail model.

Primary visual/dimensional references inspected:

- David Byrden, https://tiger1.info/EN/Hull-dimensions.html — front section,
  longitudinal nose/rear sections; bare upper hull width 3.140 m, lower hull
  1.920 m, track-centre spacing 2.622 m, combat track 0.725 m. German drawings
  and museum surveys are distinguished in the source. No fittings in width.
- https://tiger1.info/EN/Roof-height.html — late roof diagram: belly clearance
  0.485 m, hull height 1.280 m, turret gap 0.010 m, turret height 0.830 m,
  turret roof elevation 2.655 m. Cupola/antenna excluded.
- https://tiger1.info/EN/Turret-asymmetry.html — top, side, front edge and 3/4
  views: rear outside radius 1.160 m; tangent wall angles 14.5° / 20°;
  gun axis and sloping forward roof. Side profile depicts 0.815 m earlier roof;
  late pass uses 0.830 m from the late-roof source.
- https://tiger1.info/EN/Turret-dimensions.html — front/mantlet reference;
  asymmetric gun opening and 0.110 m asymmetry, not a centred generic cylinder.
- https://tiger1.info/EN/Suspension-main-axes.html — axle layout, 0.515 m
  station spacing; do not confuse torsion-bar axes with wheel centres.
- The Tank Museum, https://tankmuseum.org/tiger-wheels/ — steel wheels from
  February 1944, diameter 0.800 m, 16 wheels per side in eight paired stations.
- https://commons.wikimedia.org/wiki/File:Tiger_I_Saumur_1.JPG — Matthias
  Holländer, 2011, CC0, museum front 3/4 reference. Narrow transport tracks on
  museum photographs are not the combat-width target.
- https://commons.wikimedia.org/wiki/File:Panzerkampfwagen_VI_in_the_Mus%C3%A9e_des_Blind%C3%A9s_-_back.jpg
  — Shonagon, 2018, CC0, rear/loader hatch/exhaust and stowage arrangement.

Copyrighted Byrden drawings are retained only under ignored data/local, never
redistributed. The source `.blend` may reference these local image files without
packing them; the exported GLB contains original geometry only. Orthographic
reference empties are excluded from export.

Remaining acceptance gaps before a finished asset: fully dimensioned longitudinal
hull/turret-ring placement, exact cupola and late mantlet, complete barrel/muzzle
brake drawings, engine deck top survey, final suspension link arrangement,
secondary equipment and visual human recognition review. Those dimensions are
explicitly provisional; no whole-vehicle historical tolerance PASS is claimed.
