// Ajedrez Extendido - Piezas para impresión 3D
// Unidades: milímetros. Todas las piezas tienen base de 28 mm de diámetro,
// de modo que un único anillo de extensión sirve para todas.
// Uso: openscad -o rey.stl -D 'pieza="rey"' ajedrez11x11.scad

pieza = "conjunto";
$fn = 96;
ESCALA = 1.4;     // 1.4 = tamaño de torneo (Rey de 97 mm, casillas de 55 mm)

BASE_R = 14;      // radio de la base de todas las piezas
HOLGURA = 0.35;   // juego entre la base y el anillo de promoción

// ---------------------------------------------------------------- utilidades
function qb(p0, p1, p2, n = 12) = [for (i = [0:n]) let(t = i / n)
    (1 - t) * (1 - t) * p0 + 2 * (1 - t) * t * p1 + t * t * p2];

// convierte puntos del dibujo (lienzo 100x100, y hacia abajo) a mm en el plano XZ
function m(pts, s, y0, z0) = [for (p = pts) [(p[0] - 50) * s, (y0 - p[1]) * s + z0]];

module plano_xz(grosor) {           // extruye un perfil 2D del plano XZ con un grosor en Y
    rotate([90, 0, 0]) linear_extrude(height = grosor, center = true) children();
}

// pie común: base con bisel + escocia
module pie() {
    rotate_extrude() polygon([[0, 0], [BASE_R, 0], [BASE_R, 3.2], [BASE_R - 0.8, 4.2],
                              [11.5, 4.6], [11, 5.6], [0, 5.6]]);
}

// cuerpo torneado: radio inferior, radio superior, altura de cuello, collar
module cuerpo(r0, r1, h, rc = 9, hc = 3) {
    rotate_extrude() polygon([[0, 5], [r0, 5], [r0 - 0.6, 7], [r1, h - (rc - r1)], [rc, h], [rc, h + hc],
                              [r1 - 0.5, h + hc + 0.6], [0, h + hc + 0.6]]);
}

// ---------------------------------------------------------------- piezas
module peon() {
    pie();
    cuerpo(9.5, 5, 24, 7.5, 2.6);
    translate([0, 0, 27]) cylinder(r = 4, h = 3);
    translate([0, 0, 34.5]) sphere(r = 7, $fn = 64);
}

module guardian() {
    pie();
    cuerpo(9, 5.2, 28, 7.2, 2.6);
    translate([0, 0, 31]) cylinder(r = 4, h = 3);
    translate([0, 0, 38.5]) sphere(r = 7, $fn = 64);
    // escudo frontal: del tamaño del cuerpo, con cruz en relieve
    sh = concat([[26, 40], [74, 40], [74, 62]], qb([74, 82], [74, 82], [50, 94]),
                qb([50, 94], [26, 82], [26, 62]));
    translate([0, -7.0, 0]) {
        plano_xz(3) polygon(m(sh, 0.47, 94, 4.5));
        translate([0, -1.9, 0]) plano_xz(1) {
            polygon(m([[47.5, 46], [52.5, 46], [52.5, 86], [47.5, 86]], 0.47, 94, 4.5));
            polygon(m([[34, 58.5], [66, 58.5], [66, 63.5], [34, 63.5]], 0.47, 94, 4.5));
        }
    }
}

module torre() {
    pie();
    rotate_extrude() polygon([[0, 5], [11, 5], [10.4, 7], [9.4, 34], [11.4, 36], [11.4, 47], [0, 47]]);
}
module torre_almenas() {
    difference() {
        torre();
        translate([0, 0, 43]) cylinder(r = 7.4, h = 10);
        for (a = [0:60:359]) rotate([0, 0, a]) translate([0, -2.1, 42]) cube([15, 4.2, 10]);
    }
}

module alfil() {
    pie();
    cuerpo(10, 5.8, 32, 8.5, 3);
    difference() {
        rotate_extrude() polygon(concat([[0, 35.6], [6.2, 35.6]], qb([6.2, 35.6], [9.6, 43], [0, 53])));
        translate([1.2, -10, 44]) rotate([0, 32, 0]) cube([1.8, 20, 12]);   // ranura de la mitra
    }
    translate([0, 0, 54.5]) sphere(r = 2.6, $fn = 40);
}

module rey() {
    pie();
    cuerpo(10.5, 6.4, 40, 9.2, 3);
    rotate_extrude() polygon(concat([[0, 43.6], [7.4, 43.6], [8.2, 48]], qb([8.2, 48], [8, 56], [0, 57])));
    translate([-2, -2, 55]) cube([4, 4, 14]);
    translate([-5.5, -2, 61]) cube([11, 4, 4]);
}

module dama() {
    pie();
    cuerpo(10.5, 6.4, 36, 9, 3);
    difference() {
        rotate_extrude() polygon([[0, 39.6], [6.5, 39.6], [10.8, 52], [0, 52]]);
        translate([0, 0, 47]) cylinder(r1 = 4, r2 = 8.8, h = 5.1);
        for (a = [22.5:45:359]) rotate([0, 0, a]) translate([10, 0, 52]) rotate([0, 45, 0]) cube([4, 6, 4], center = true);
    }
    for (a = [0:45:359]) rotate([0, 0, a]) translate([10.2, 0, 52.6]) sphere(r = 2.2, $fn = 32);
    translate([0, 0, 45]) cylinder(r1 = 4.5, r2 = 2, h = 11);
    translate([0, 0, 58]) sphere(r = 3, $fn = 40);
}

module elip(c, r) { translate(c) scale(r) sphere(r = 1, $fn = 40); }

module caballo() {
    // Caballo de estilo Staunton: cuello grueso y arqueado, cabeza inclinada hacia abajo,
    // mejillas anchas, hocico corto con boca abierta, orejas pequeñas hacia atrás,
    // crin en relieve con mechones, flequillo, ojos y fosas nasales.
    pie();
    rotate_extrude() polygon([[0, 5], [11, 5], [10.4, 7], [9, 9], [10.8, 10.8], [10.8, 12.4], [0, 12.4]]);
    mane = [for (t = [0:0.1:1.001]) [-9.6 + 4.0 * t * t - 1.0 * sin(180 * t), 14 + 32 * t]];
    difference() {
        union() {
            hull() { elip([0, 0, 13.5], [8.5, 6.8, 3]); elip([3.6, 0, 18.5], [4.6, 6.2, 4.6]);
                     elip([-4, 0, 33], [6.2, 6, 5]); }                                   // cuello y pecho
            hull() { elip([-4, 0, 33], [6.2, 6, 5]); elip([-0.6, 0, 41], [6.8, 6, 6]); }  // nuca
            hull() { elip([-0.6, 0, 41], [6.8, 6, 6]); elip([10.4, 0, 30.6], [4.3, 4.4, 3.6]); } // cabeza
            hull() { elip([2.5, 0, 33.4], [5.6, 6.3, 4.6]); elip([9, 0, 27.6], [3.4, 3.5, 1.8]); } // mejillas y barbilla
            for (sy = [-1, 1]) hull() {                                                   // orejas redondeadas
                translate([-3.3, sy * 2.6, 45.2]) scale([1.5, 0.85, 1.1]) sphere(r = 2.2, $fn = 28);
                translate([-5.1, sy * 2.75, 48.6]) scale([1.25, 0.8, 1]) sphere(r = 1.6, $fn = 24);
            }
            for (k = [0:len(mane) - 2]) hull() {                                          // crin
                translate([mane[k][0], 0, mane[k][1]]) scale([1, 1.55, 1]) sphere(r = 2.2, $fn = 20);
                translate([mane[k + 1][0], 0, mane[k + 1][1]]) scale([1, 1.55, 1]) sphere(r = 2.2, $fn = 20);
            }
            elip([-1.2, 0, 46.6], [2.2, 1.6, 1.4]);                                       // flequillo
        }
        for (k = [1:len(mane) - 2]) for (sy = [-1, 1])                                   // mechones
            translate([mane[k][0] - 0.4, sy * 3.2, mane[k][1]]) rotate([0, -38, 0]) cube([5.5, 1.4, 0.8], center = true);
        for (sy = [-1, 1]) translate([3.6, sy * 5.0, 42]) sphere(r = 1.5, $fn = 24);     // cuencas
        for (sy = [-1, 1]) translate([-2.5, sy * 2.75, 47.4]) scale([1, 0.6, 1.4]) sphere(r = 1, $fn = 20); // pabellón de la oreja
        for (sy = [-1, 1]) translate([13.6, sy * 2.0, 31.9]) sphere(r = 1.0, $fn = 20);  // fosas nasales
        translate([10.2, -6, 28.4]) rotate([0, 12, 0]) cube([8, 12, 1.1]);              // boca
    }
    for (sy = [-1, 1]) translate([3.6, sy * 4.3, 42]) sphere(r = 1.2, $fn = 20);         // ojos
}

module arzobispo() {            // copa en media luna con una bola, como la pieza 3D de Capablanca
    pie();
    cuerpo(10, 5.8, 32, 8.5, 3);
    translate([0, 0, 31.4]) rotate_extrude() translate([6.3, 0]) circle(r = 1.1, $fn = 24);   // aro bajo el collar
    translate([0, 0, 35]) cylinder(r1 = 3.4, r2 = 2.9, h = 4);                                    // cuello
    s = 0.5;                                                     // dibujo del juego (lienzo 100x100) a mm
    luna = concat(qb([27, 14], [26, 39], [50, 39.5]), qb([50, 39.5], [74, 39], [73, 14]),
                  qb([73, 14], [68, 26], [50, 27]), qb([50, 27], [32, 26], [27, 14]));
    minkowski() {                                                // copa gruesa con los bordes redondeados
        plano_xz(5.2) offset(delta = -0.9) polygon(m(luna, s, 44, 35.6));
        sphere(r = 0.9, $fn = 16);
    }
    translate([0, 0, (44 - 27) * s + 35.6 - 1]) cylinder(r1 = 1.7, r2 = 1.3, h = 3.6);           // cuello de la bola
    translate([0, 0, (44 - 17) * s + 35.6]) sphere(r = 2.9, $fn = 48);                            // bola
}

module canciller() {            // sello de lacre (pieza totalmente torneada)
    pie();
    rotate_extrude() polygon(concat(
        [[0, 5], [11, 5], [10.4, 7], [9.4, 29], [11.6, 31], [11.6, 34], [9.6, 34.6], [9.6, 38.5], [3.4, 39.6],
         [3.4, 44.5], [9.2, 50.3]], qb([9.2, 50.3], [9.2, 57], [0, 57])));
}

module catapulta() {            // brazo curvo con cuchara
    pie();
    cuerpo(10, 5.8, 32, 8.5, 3);
    s = 0.5;
    arm = concat(qb([45, 41], [46, 24], [34, 16]), [[39, 10]], qb([39, 10], [56, 20], [56, 41]));
    cup = concat(qb([16, 9], [17, 23], [29, 22]), qb([29, 22], [39, 20], [39, 12]));
    translate([0, 0, 0]) plano_xz(6.5) polygon(m(arm, s, 41, 34.5));
    plano_xz(8) polygon(m(cup, s, 41, 34.5));
    translate([(27 - 50) * s, 0, (41 - 9) * s + 34.5]) sphere(r = 3.7, $fn = 48);
}

// ---------------------------------------------------------------- anillo de promoción
module anillo_promocion() {
    E = ESCALA;
    ri = BASE_R * E + HOLGURA;      // la holgura no se escala
    w = 3.2 * E; h = 5.6 * E; f = 1.2 * E;
    difference() {
        rotate_extrude() polygon([[0, 0], [ri + w, 0], [ri + w, h - 1.2 * E], [ri + w - 0.8 * E, h], [0, h]]);
        translate([0, 0, f]) cylinder(r = ri, h = 20 * E);
        translate([0, 0, h - 0.7 * E]) cylinder(r1 = ri, r2 = ri + 0.8 * E, h = 0.8 * E);   // chaflán de entrada
        for (a = [0:30:359]) rotate([0, 0, a]) translate([ri + w, 0, h / 2]) rotate([0, 0, 45]) cube([E, E, 2.4 * E], center = true);
    }
}

// ---------------------------------------------------------------- selección
if (pieza == "anillo") anillo_promocion();
else scale(ESCALA) {
    if (pieza == "rey") rey();
    if (pieza == "dama") dama();
    if (pieza == "torre") torre_almenas();
    if (pieza == "alfil") alfil();
    if (pieza == "caballo") caballo();
    if (pieza == "arzobispo") arzobispo();
    if (pieza == "canciller") canciller();
    if (pieza == "catapulta") catapulta();
    if (pieza == "guardian") guardian();
    if (pieza == "peon") peon();
}
if (pieza == "conjunto") {}
if (pieza == "conjunto") {
    nombres = ["rey", "dama", "torre", "alfil", "caballo", "arzobispo", "canciller", "catapulta", "guardian", "peon"];
    for (i = [0:9]) translate([(i % 5) * 40, -floor(i / 5) * 40, 0]) color([0.94, 0.92, 0.86]) {
        if (i == 0) rey(); if (i == 1) dama(); if (i == 2) torre_almenas(); if (i == 3) alfil();
        if (i == 4) caballo(); if (i == 5) arzobispo(); if (i == 6) canciller(); if (i == 7) catapulta();
        if (i == 8) guardian(); if (i == 9) peon();
    }
    translate([200, 0, 0]) color([0.85, 0.65, 0.13]) anillo_promocion();
    translate([200, -40, 0]) { color([0.85, 0.65, 0.13]) anillo_promocion(); translate([0, 0, 1.2]) color([0.94, 0.92, 0.86]) torre_almenas(); }
}
