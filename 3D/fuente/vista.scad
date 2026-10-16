use <ajedrez11x11.scad>
pieza = "rey";
$fn = 72;
C = [0.93, 0.90, 0.83];
E = 1.4;  // la misma ESCALA que ajedrez11x11.scad (tamaño de torneo): piezas y anillo a escala real
G = [0.85, 0.63, 0.12];
if (pieza == "rey") scale(E) color(C) rey();
if (pieza == "dama") scale(E) color(C) dama();
if (pieza == "torre") scale(E) color(C) torre_almenas();
if (pieza == "alfil") scale(E) color(C) alfil();
if (pieza == "caballo") scale(E) color(C) caballo();
if (pieza == "arzobispo") scale(E) color(C) arzobispo();
if (pieza == "canciller") scale(E) color(C) canciller();
if (pieza == "catapulta") scale(E) color(C) catapulta();
if (pieza == "guardian") scale(E) color(C) guardian();
if (pieza == "peon") scale(E) color(C) peon();
if (pieza == "anillo") color(G) anillo_promocion();
if (pieza == "extendida") { color(G) anillo_promocion(); translate([0,0,1.7]) scale(E) color(C) catapulta(); }
