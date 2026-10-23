#!/usr/bin/env python3
"""Matinale des Sciences - section « Comprendre » : les bases de la physique et de la chimie.

Ce fichier est la source du contenu. Il écrit site/data/bases.json (lu par l'appli, gardé hors ligne).
Usage : python3 scripts/bases.py [--out site/data/bases.json]

Chaque notion a trois niveaux :
  kid    : « Pour tous, dès 10 ans »      (phrases courtes, images du quotidien)
  more   : « Pour aller plus loin »        (vocabulaire précis, niveau collège/lycée)
  expert : « Niveau ingénieur »            (formules, ordres de grandeur, domaines de validité)
Les schémas sont en SVG : les couleurs viennent des classes (ln, lt, ac, sf, c0..c4, tb, ts, tw),
définies dans la page, pour s'adapter au thème clair et au thème sombre.
"""
import argparse
import json
import math
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))


def defs(n, extra=''):
    """Pointes de flèches propres à chaque schéma (a- : encre, b- : couleur d'accent)."""
    m = ('<marker id="{p}-{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
         '<path d="M0,0L10,5L0,10z" class="{c}"/></marker>')
    return '<defs>' + m.format(p='a', n=n, c='mk') + m.format(p='b', n=n, c='mka') + extra + '</defs>'


def svg(n, w, h, label, body, extra_defs=''):
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}" xmlns="http://www.w3.org/2000/svg">'
            + defs(n, extra_defs) + body + '</svg>')


# ------------------------------------------------------------------ schémas

def svg_atome():
    nuc = ''.join(f'<circle cx="{x}" cy="{y}" r="8" class="{c}"/>' for x, y, c in
                  [(181, 100, 'c0'), (174, 105, 'c2'), (188, 107, 'c0'), (169, 116, 'c0'), (180, 117, 'c2'), (192, 118, 'c2')])
    b = ('<ellipse cx="180" cy="110" rx="110" ry="38" class="lt dash"/>'
         '<ellipse cx="180" cy="110" rx="110" ry="38" class="lt dash" transform="rotate(55 180 110)"/>'
         '<ellipse cx="180" cy="110" rx="110" ry="38" class="lt dash" transform="rotate(-55 180 110)"/>'
         + nuc +
         '<circle cx="290" cy="110" r="6" class="c3"/><circle cx="117" cy="20" r="6" class="c3"/><circle cx="211" cy="132" r="6" class="c3"/>'
         '<path d="M196,122 L260,184" class="lt"/><text x="264" y="190">noyau</text>'
         '<path d="M72,30 L110,22" class="lt"/><text x="18" y="34">électron</text>'
         '<text x="350" y="24" text-anchor="end" class="ts">pas à l\'échelle</text>'
         '<circle cx="24" cy="211" r="6" class="c2"/><text x="34" y="215" class="ts">proton</text>'
         '<circle cx="104" cy="211" r="6" class="c0"/><text x="114" y="215" class="ts">neutron</text>'
         '<circle cx="190" cy="211" r="6" class="c3"/><text x="200" y="215" class="ts">électron</text>')
    return svg('atome', 360, 230, "Schéma d'un atome : un noyau de protons et de neutrons, entouré d'électrons", b)


def svg_etats():
    solid = ''.join(f'<circle cx="{x}" cy="{y}" r="8" class="c1"/>' for x in (23, 41, 59, 77) for y in (58, 76, 94, 112))
    liq = ''.join(f'<circle cx="{x}" cy="{y}" r="7" class="c1"/>' for x, y in
                  [(152, 118), (168, 121), (184, 118), (200, 121), (212, 108), (158, 102), (175, 104), (191, 101), (207, 92), (165, 86), (183, 88), (150, 88)])
    gas = ''.join(f'<circle cx="{x}" cy="{y}" r="7" class="c1"/><path d="M{x - 9},{y - 4} l-9,-4 M{x - 9},{y + 2} l-7,0" class="lt"/>' for x, y in
                  [(292, 56), (336, 68), (304, 96), (340, 112), (288, 120), (322, 86)])
    b = ('<text x="50" y="30" text-anchor="middle" class="tb">Solide</text>'
         '<text x="180" y="30" text-anchor="middle" class="tb">Liquide</text>'
         '<text x="310" y="30" text-anchor="middle" class="tb">Gaz</text>'
         '<rect x="10" y="40" width="80" height="90" rx="10" class="ln sf"/>'
         '<rect x="140" y="40" width="80" height="90" rx="10" class="ln sf"/>'
         '<rect x="270" y="40" width="80" height="90" rx="10" class="ln sf"/>'
         + solid + liq + gas +
         '<text x="115" y="152" text-anchor="middle" class="ts">fusion</text>'
         '<text x="245" y="152" text-anchor="middle" class="ts">vaporisation</text>'
         '<path d="M50,160 H310" class="ac" marker-end="url(#b-etats)"/>'
         '<path d="M310,190 H50" class="ln" marker-end="url(#a-etats)"/>'
         '<text x="115" y="210" text-anchor="middle" class="ts">solidification</text>'
         '<text x="245" y="210" text-anchor="middle" class="ts">condensation</text>')
    return svg('etats', 360, 222, 'Les trois états de la matière et leurs changements', b)


def svg_energie():
    L, a = 130, math.radians(40)
    lx, ly = 180 - L * math.sin(a), 20 + L * math.cos(a)
    rx = 180 + L * math.sin(a)

    def bars(cx, ep, ec):
        out = ''
        for dx, val, cls, lab in ((-11, ep, 'c2', 'Ep'), (11, ec, 'c3', 'Ec')):
            h = max(2, 40 * val)
            out += f'<rect x="{cx + dx - 5}" y="{210 - h:.1f}" width="10" height="{h:.1f}" class="{cls}"/>'
            out += f'<text x="{cx + dx}" y="225" text-anchor="middle" class="ts">{lab}</text>'
        return out
    b = ('<path d="M150,20 H210" class="ln" style="stroke-width:3"/>'
         f'<path d="M180,20 L{lx:.1f},{ly:.1f}" class="lt dash"/><path d="M180,20 L180,150" class="ln"/><path d="M180,20 L{rx:.1f},{ly:.1f}" class="lt dash"/>'
         f'<path d="M{lx:.1f},{ly:.1f} A{L},{L} 0 0 0 {rx:.1f},{ly:.1f}" class="lt dash"/>'
         f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="11" class="c1"/><circle cx="180" cy="150" r="11" class="c1"/><circle cx="{rx:.1f}" cy="{ly:.1f}" r="11" class="c1"/>'
         + bars(lx, 1, 0) + bars(180, 0, 1) + bars(rx, 1, 0) +
         '<rect x="10" y="12" width="10" height="10" class="c2"/><text x="26" y="21" class="ts">Ep : hauteur</text>'
         '<rect x="10" y="30" width="10" height="10" class="c3"/><text x="26" y="39" class="ts">Ec : vitesse</text>')
    return svg('energie', 360, 232, "Un pendule : l'énergie de hauteur se change en énergie de mouvement, puis l'inverse", b)


def svg_forces():
    hatch = ''.join(f'<path d="M{x},170 l-8,10" class="lt"/>' for x in list(range(30, 131, 20)) + list(range(250, 341, 20)))
    b = ('<path d="M20,170 H340" class="ln"/>' + hatch +
         '<rect x="140" y="110" width="80" height="60" rx="4" class="ln sf"/><text x="180" y="146" text-anchor="middle" class="tb">m</text>'
         '<path d="M62,140 H136" class="ac" marker-end="url(#b-forces)"/><text x="99" y="130" text-anchor="middle">poussée F</text>'
         '<path d="M150,184 H98" class="ln" marker-end="url(#a-forces)"/><text x="124" y="201" text-anchor="middle" class="ts">frottements</text>'
         '<path d="M180,140 V212" class="ln" marker-end="url(#a-forces)"/><text x="188" y="208" class="ts">poids P</text>'
         '<path d="M180,108 V52" class="ln" marker-end="url(#a-forces)"/><text x="188" y="60" class="ts">réaction du sol R</text>'
         '<path d="M236,95 H300" class="ac dash" marker-end="url(#b-forces)"/><text x="268" y="86" text-anchor="middle" class="ts">accélération a</text>'
         '<text x="340" y="28" text-anchor="end" class="tb">ΣF = m × a</text>')
    return svg('forces', 360, 222, 'Les forces sur un bloc poussé : poussée, frottements, poids et réaction du sol', b)


def svg_gravitation():
    b = ('<path d="M252.6,12.2 A160,160 0 0 1 252.6,217.8" class="lt dash"/>'
         '<circle cx="130" cy="115" r="45" class="ln sf"/><text x="130" y="120" text-anchor="middle" class="tb">Terre</text>'
         '<circle cx="290" cy="115" r="14" class="c0"/><text x="290" y="148" text-anchor="middle" class="ts">Lune</text>'
         '<path d="M274,115 H180" class="ac" marker-end="url(#b-grav)"/><text x="227" y="107" text-anchor="middle" class="ts">attraction</text>'
         '<path d="M290,99 V40" class="ln" marker-end="url(#a-grav)"/><text x="298" y="52" class="ts">vitesse</text>'
         '<circle cx="130" cy="30" r="6" class="c4"/><path d="M130,24 l2,-5" class="lt"/>'
         '<path d="M130,39 V64" class="ac" marker-end="url(#b-grav)"/><text x="142" y="34" class="ts">pomme</text>')
    return svg('grav', 360, 225, "La même attraction fait tomber la pomme et garde la Lune en orbite autour de la Terre", b)


def svg_lumiere():
    cols = ['#e53935', '#fb8c00', '#fdd835', '#43a047', '#1e88e5', '#8e24aa']
    rays = ''
    for i, c in enumerate(cols):
        s = 0.45 + 0.03 * i
        ex, ey = 200 + 50 * s, 85 + 90 * s
        rays += (f'<path d="M175,130 L{ex:.1f},{ey:.1f}" style="stroke:{c};stroke-width:1.4;fill:none"/>'
                 f'<path d="M{ex:.1f},{ey:.1f} L345,{118 + 17 * i}" style="stroke:{c};stroke-width:2.4;fill:none"/>')
    b = ('<path d="M150,175 L250,175 L200,85 Z" class="ln sf"/>'
         '<path d="M20,100 L175,130" class="ln" style="stroke-width:3"/><text x="20" y="90">lumière blanche</text>'
         + rays +
         '<text x="345" y="110" text-anchor="end" class="ts">rouge ≈ 700 nm</text>'
         '<text x="345" y="222" text-anchor="end" class="ts">violet ≈ 400 nm</text>'
         '<text x="200" y="196" text-anchor="middle" class="ts">prisme</text>')
    return svg('lum', 360, 230, 'Un prisme décompose la lumière blanche en couleurs, du rouge au violet', b)


def svg_son():
    xs, x = [], 76.0
    while x < 345:
        xs.append(x)
        x += 4 + 10 * (1 - math.cos(2 * math.pi * (x - 100) / 70)) / 2
    lines = ''.join(f'<path d="M{v:.1f},70 V150" class="lt"/>' for v in xs)
    b = ('<rect x="16" y="88" width="16" height="44" rx="3" class="c0"/><path d="M32,88 L58,66 V154 L32,132 Z" class="ln sf"/>'
         + lines +
         '<path d="M240,44 V66" class="lt"/><text x="240" y="40" text-anchor="middle" class="ts">compression</text>'
         '<path d="M275,62 V66" class="lt"/><text x="275" y="58" text-anchor="middle" class="ts">détente</text>'
         '<path d="M100,170 H170" class="ln" marker-start="url(#a-son)" marker-end="url(#a-son)"/>'
         '<text x="135" y="188" text-anchor="middle" class="ts">λ : longueur d\'onde</text>'
         '<path d="M80,210 H190" class="ac" marker-end="url(#b-son)"/><text x="198" y="214" class="ts">l\'onde avance</text>')
    return svg('son', 360, 222, "Une onde sonore : des zones d'air comprimé et détendu qui se propagent", b)


def svg_electricite():
    b = ('<path d="M60,100 V50 H160" class="ln"/><path d="M200,50 H300 V94" class="ln"/><path d="M300,126 V170 H60 V112" class="ln"/>'
         '<path d="M44,100 H76" class="ln" style="stroke-width:2"/><path d="M52,112 H68" class="ln" style="stroke-width:4"/>'
         '<text x="84" y="104" class="tb">+</text><text x="84" y="120" class="tb">−</text><text x="10" y="110" class="ts">pile</text>'
         '<circle cx="160" cy="50" r="3" class="c0"/><circle cx="200" cy="50" r="3" class="c0"/><path d="M160,50 L198,50" class="ln" style="stroke-width:2.6"/>'
         '<text x="180" y="38" text-anchor="middle" class="ts">interrupteur fermé</text>'
         '<circle cx="300" cy="110" r="16" class="ln sf"/><path d="M289,99 L311,121 M311,99 L289,121" class="ln"/><text x="322" y="114" class="ts">lampe</text>'
         '<path d="M84,64 H144" class="ac" marker-end="url(#b-elec)"/><text x="114" y="80" text-anchor="middle" class="ts">sens du courant I</text>'
         '<path d="M130,158 H200" class="ln dash" marker-end="url(#a-elec)"/><text x="165" y="150" text-anchor="middle" class="ts">électrons</text>'
         '<text x="200" y="116" text-anchor="middle" class="tb">U = R × I</text>')
    return svg('elec', 360, 200, 'Un circuit électrique simple : une pile, un interrupteur et une lampe', b)


def svg_chaleur():
    grad = '<linearGradient id="g-chaleur" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#e53935"/><stop offset="1" stop-color="#90caf9"/></linearGradient>'
    flame = lambda x, y: f'<path d="M{x},{y} q-7,-10 0,-20 q10,8 5,20 z" class="c2"/>'
    wave = lambda x, y: (f'<path d="M{x},{y} c4,-6 8,6 12,0 s8,6 12,0 s8,6 12,0 s8,6 12,0" class="ac" '
                         f'transform="rotate(38 {x} {y})" marker-end="url(#b-chaleur)"/>')
    rays = ''.join(f'<path d="M{265 + 20 * math.cos(t):.1f},{62 + 20 * math.sin(t):.1f} l{6 * math.cos(t):.1f},{6 * math.sin(t):.1f}" class="lt"/>'
                   for t in [k * math.pi / 4 for k in range(8)])
    b = ('<text x="60" y="22" text-anchor="middle" class="tb">Conduction</text>'
         '<text x="180" y="22" text-anchor="middle" class="tb">Convection</text>'
         '<text x="300" y="22" text-anchor="middle" class="tb">Rayonnement</text>'
         '<rect x="12" y="95" width="96" height="18" rx="4" class="lt" style="fill:url(#g-chaleur)"/>' + flame(22, 142) +
         '<path d="M24,80 H100" class="ac" marker-end="url(#b-chaleur)"/>'
         '<text x="40" y="160" class="ts">chaud</text><text x="108" y="132" text-anchor="end" class="ts">froid</text>'
         '<text x="60" y="180" text-anchor="middle" class="ts">de proche</text><text x="60" y="193" text-anchor="middle" class="ts">en proche</text>'
         '<path d="M135,55 V140 Q135,150 145,150 H215 Q225,150 225,140 V55" class="ln"/><path d="M135,68 H225" class="lt dash"/>'
         '<path d="M180,140 V84" class="ac" marker-end="url(#b-chaleur)"/>'
         '<path d="M150,84 V138" class="ln" marker-end="url(#a-chaleur)"/><path d="M210,84 V138" class="ln" marker-end="url(#a-chaleur)"/>'
         + flame(168, 172) + flame(190, 172) +
         '<text x="180" y="192" text-anchor="middle" class="ts">le chaud monte,</text><text x="180" y="205" text-anchor="middle" class="ts">le froid descend</text>'
         '<circle cx="265" cy="62" r="14" class="c2"/>' + rays + wave(282, 84) + wave(270, 100) +
         '<path d="M250,160 H350" class="ln"/>'
         '<text x="300" y="180" text-anchor="middle" class="ts">même à travers</text><text x="300" y="193" text-anchor="middle" class="ts">le vide</text>')
    return svg('chaleur', 360, 212, 'Les trois façons dont la chaleur se déplace : conduction, convection et rayonnement', b, grad)


def svg_molecules():
    b = ('<path d="M150,110 L106.5,143.7 M150,110 L193.5,143.7" class="ln" style="stroke-width:5"/>'
         '<path d="M292,150 L330,128 M292,150 L318,186" class="ln" style="stroke-width:5"/>'
         '<path d="M118.4,134.5 A40,40 0 0 0 181.6,134.5" class="lt"/>'
         '<circle cx="150" cy="110" r="26" class="c1"/><text x="150" y="116" text-anchor="middle" class="tw">O</text>'
         '<circle cx="106.5" cy="143.7" r="15" class="c3"/><text x="106.5" y="148.5" text-anchor="middle" class="tw">H</text>'
         '<circle cx="193.5" cy="143.7" r="15" class="c3"/><text x="193.5" y="148.5" text-anchor="middle" class="tw">H</text>'
         '<circle cx="292" cy="150" r="22" class="c1"/><text x="292" y="155" text-anchor="middle" class="tw">O</text>'
         '<circle cx="330" cy="128" r="13" class="c3"/><circle cx="318" cy="186" r="13" class="c3"/>'
         '<path d="M209,145 L269,150" class="ac dash"/>'
         '<text x="150" y="172" text-anchor="middle" class="ts">104,5°</text>'
         '<text x="150" y="76" text-anchor="middle" class="tb">δ−</text>'
         '<text x="86" y="150" text-anchor="end" class="tb">δ+</text><text x="200" y="180" text-anchor="middle" class="tb">δ+</text>'
         '<path d="M70,62 L125,124" class="lt"/><text x="18" y="56">liaison covalente</text>'
         '<path d="M239,152 L248,192" class="lt"/><text x="250" y="206" text-anchor="middle">liaison hydrogène</text>')
    return svg('mol', 360, 215, "Une molécule d'eau : un oxygène lié à deux hydrogènes, et une liaison hydrogène avec une molécule voisine", b)


def svg_reaction():
    def ball(x, y, r, c):
        return f'<circle cx="{x}" cy="{y}" r="{r}" class="{c}"/>'
    ch4 = ball(40, 95, 13, 'c0') + ''.join(ball(x, y, 7, 'c3') for x, y in [(40, 74), (40, 116), (19, 95), (61, 95)])
    o2 = ''.join(ball(x, y, 10, 'c2') for x, y in [(108, 78), (127, 78), (108, 112), (127, 112)])
    co2 = ball(204, 95, 10, 'c2') + ball(226, 95, 12, 'c0') + ball(248, 95, 10, 'c2')
    h2o = ''.join(ball(293, y + 12, 6, 'c3') + ball(317, y + 12, 6, 'c3') + ball(305, y, 10, 'c2') for y in (76, 112))
    b = ('<text x="180" y="28" text-anchor="middle" class="tb">CH₄ + 2 O₂ → CO₂ + 2 H₂O</text>'
         + ch4 + '<text x="82" y="101" text-anchor="middle" class="tb">+</text>' + o2 +
         '<path d="M146,95 H186" class="ln" marker-end="url(#a-react)"/>'
         + co2 + '<text x="270" y="101" text-anchor="middle" class="tb">+</text>' + h2o +
         '<text x="73" y="165" text-anchor="middle" class="ts">1 C · 4 H · 4 O</text>'
         '<text x="262" y="165" text-anchor="middle" class="ts">1 C · 4 H · 4 O</text>'
         '<text x="180" y="192" text-anchor="middle" class="tb">autant d\'atomes avant et après</text>'
         '<circle cx="40" cy="216" r="6" class="c0"/><text x="50" y="220" class="ts">carbone</text>'
         '<circle cx="130" cy="216" r="6" class="c3"/><text x="140" y="220" class="ts">hydrogène</text>'
         '<circle cx="230" cy="216" r="6" class="c2"/><text x="240" y="220" class="ts">oxygène</text>')
    return svg('react', 360, 230, "La combustion du méthane : les atomes se réarrangent, aucun ne disparaît", b)


def svg_ph():
    grad = ('<linearGradient id="g-ph" x1="0" x2="1" y1="0" y2="0">'
            + ''.join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in
                      [(0, '#d32f2f'), (.2, '#f57c00'), (.38, '#fbc02d'), (.5, '#7cb342'), (.62, '#26a69a'), (.78, '#1e88e5'), (1, '#5e35b1')])
            + '</linearGradient>')
    X = lambda v: 20 + 320 * v / 14
    ticks = ''.join(f'<text x="{X(k):.1f}" y="136" text-anchor="middle" class="ts">{k}</text>' for k in range(15))

    def up(v, lab, y, anchor='middle', dx=0):
        return f'<path d="M{X(v):.1f},{y + 4} V90" class="lt"/><text x="{X(v) + dx:.1f}" y="{y}" text-anchor="{anchor}" class="ts">{lab}</text>'

    def down(v, lab, y, anchor='middle', dx=0):
        return f'<path d="M{X(v):.1f},120 V{y - 11}" class="lt"/><text x="{X(v) + dx:.1f}" y="{y}" text-anchor="{anchor}" class="ts">{lab}</text>'
    b = ('<rect x="20" y="92" width="320" height="26" rx="6" class="lt" style="fill:url(#g-ph)"/>' + ticks
         + up(2, 'citron 2', 62) + up(5, 'café 5', 62) + up(7, 'eau pure 7', 46) + up(10, 'savon ≈ 10', 62)
         + down(3, 'vinaigre ≈ 3', 162) + down(7.4, 'sang 7,4', 162, 'end', -2) + down(8.3, 'bicarbonate 8,3', 182, 'start', 2)
         + down(12.5, 'eau de Javel ≈ 12,5', 162) + down(8.1, 'eau de mer 8,1', 202, 'start', 2)
         + '<text x="20" y="226" class="ts">← plus acide</text><text x="180" y="226" text-anchor="middle" class="ts">neutre</text>'
         '<text x="340" y="226" text-anchor="end" class="ts">plus basique →</text>')
    return svg('ph', 360, 234, 'Échelle de pH de 0 à 14 avec des exemples de la vie courante', b, grad)


# ------------------------------------------------------------------ contenu

DOMAINS = [
    {'id': 'physique', 'label': 'Physique', 'sub': 'Énergie, forces, chaleur, électricité, ondes et lumière'},
    {'id': 'chimie', 'label': 'Chimie', 'sub': 'Les atomes, les molécules et leurs transformations'},
]

START = ['atome', 'etats-matiere', 'energie']   # « Par où commencer ? »

NOTIONS = [
    # ---------------------------------------------------------------- PHYSIQUE
    {
        'id': 'energie', 'domain': 'physique', 'title': "L'énergie",
        'tagline': 'Ce qui permet de bouger, chauffer, éclairer',
        'kid': [
            "L'énergie, c'est ce qui permet de faire quelque chose : bouger, chauffer, éclairer, faire pousser une plante. "
            "Elle existe sous plusieurs formes : l'énergie du mouvement, de la chaleur, de la lumière, de l'électricité, "
            "ou l'énergie cachée dans la nourriture et dans le carburant.",
            "L'énergie ne disparaît jamais et ne se crée pas : elle se transforme. Quand tu fais du vélo, l'énergie de ton repas "
            "devient du mouvement, puis un peu de chaleur quand tu freines.",
            "Sur Terre, presque toute notre énergie vient du Soleil : il fait pousser les plantes, chauffe l'air pour créer le vent "
            "et évapore l'eau qui retombe en pluie dans les barrages.",
        ],
        'dyk': "Une barre chocolatée (environ 1 000 kJ) contient assez d'énergie pour monter un adulte de 70 kg en haut de la tour Eiffel "
               "quatre à cinq fois. Mais nos muscles n'en transforment qu'environ un quart en mouvement : en vrai, on y arrive à peine une fois, "
               "le reste part en chaleur.",
        'more': [
            "On mesure l'énergie en joules (J). Un joule, c'est à peu près l'énergie qu'il faut pour soulever une pomme de 100 g d'un mètre. "
            "Les factures d'électricité utilisent le kilowattheure : 1 kWh = 3,6 millions de joules, l'énergie consommée par un radiateur "
            "de 1 000 watts pendant une heure.",
            "Il ne faut pas confondre énergie et puissance. La puissance, en watts (W), dit à quelle vitesse l'énergie est transformée : "
            "1 W = 1 joule par seconde.",
            "À chaque transformation, une partie de l'énergie part en chaleur difficile à récupérer : un moteur à essence n'utilise "
            "qu'environ un quart à un tiers de l'énergie du carburant pour faire avancer la voiture.",
        ],
        'expert': [
            "Premier principe de la thermodynamique : pour un système fermé, ΔU = W + Q (travail et chaleur reçus comptés positivement). "
            "L'énergie totale d'un système isolé se conserve.",
            "Énergie cinétique Ec = ½ m v², énergie potentielle de pesanteur Ep = m g h (près du sol), énergie électrique E = U I t, "
            "énergie de masse E = m c² : 1 g de matière équivaut à 9 × 10¹³ J, soit environ 21 kilotonnes de TNT.",
            "Le second principe impose que l'entropie d'un système isolé ne diminue pas : convertir de la chaleur en travail a donc un "
            "rendement limité. Pour un moteur thermique entre une source chaude T_c et une source froide T_f, le rendement maximal est "
            "celui de Carnot, η = 1 − T_f / T_c (températures en kelvins).",
        ],
        'formulas': [
            {'f': 'Ec = ½ · m · v²', 'l': 'énergie de mouvement (J, kg, m/s)'},
            {'f': 'Ep = m · g · h', 'l': 'énergie de hauteur près du sol'},
            {'f': 'P = E / t', 'l': 'puissance (W = J/s)'},
            {'f': 'η_max = 1 − T_f / T_c', 'l': 'rendement de Carnot'},
            {'f': 'E = m · c²', 'l': 'équivalence masse-énergie'},
        ],
        'numbers': [
            {'v': '1 kWh = 3,6 MJ', 'l': 'énergie d\'un radiateur de 1 kW pendant 1 h'},
            {'v': '1 kcal = 4,184 kJ', 'l': 'la « calorie » des étiquettes'},
            {'v': '≈ 1 361 W/m²', 'l': 'puissance du Soleil reçue au-dessus de l\'atmosphère'},
        ],
        'exp': {
            'title': 'Le pendule qui ne triche pas',
            'steps': [
                "Attache une gomme ou un petit objet au bout d'un fil, et tiens l'autre bout immobile.",
                "Écarte la gomme jusqu'au bout de ton nez, sans la pousser, puis lâche-la et ne bouge plus.",
                "Elle revient… mais jamais plus loin que ton nez ! Sa hauteur se change en vitesse, puis la vitesse redevient hauteur. "
                "Elle ne peut pas gagner d'énergie, et en perd un peu à cause de l'air.",
            ],
            'safety': 'Utilise un objet léger et mou.',
        },
        'svg': svg_energie(),
        'caption': "En haut, le pendule a toute son énergie sous forme de hauteur (Ep) ; en bas, sous forme de vitesse (Ec). "
                   "Sans frottements, la somme Ep + Ec resterait constante.",
        'related': ['forces-mouvement', 'chaleur-temperature', 'electricite', 'gravitation'],
    },
    {
        'id': 'forces-mouvement', 'domain': 'physique', 'title': 'Les forces et le mouvement',
        'tagline': 'Pourquoi les choses bougent, accélèrent ou s\'arrêtent',
        'kid': [
            "Une force, c'est une poussée ou une traction. Quand tu lances un ballon, tu exerces une force ; quand il retombe, "
            "c'est la Terre qui l'attire.",
            "Un objet ne change pas de vitesse tout seul : il faut une force pour le mettre en mouvement, l'accélérer, le freiner ou "
            "le faire tourner. Si une voiture freine d'un coup, ton corps continue vers l'avant : c'est pour ça qu'on attache sa ceinture.",
            "Plus un objet est lourd, plus il faut forcer pour changer sa vitesse : pousser un caddie vide est facile, un caddie plein "
            "beaucoup moins.",
        ],
        'dyk': "Quand tu sautes, tu pousses la Terre vers le bas pendant qu'elle te pousse vers le haut. Elle bouge aussi ! Mais comme elle "
               "est environ cent mille milliards de milliards de fois plus lourde que toi, elle se déplace de plus de dix mille milliards "
               "de fois moins que la taille d'un atome.",
        'more': [
            "Isaac Newton a résumé le mouvement en trois lois (1687). 1. Principe d'inertie : sans force, ou si les forces s'annulent, "
            "un objet garde sa vitesse, en ligne droite. 2. Une force produit une accélération d'autant plus grande que la masse est "
            "petite : F = m × a. 3. Action-réaction : si A pousse B, B pousse A avec une force égale et opposée.",
            "La troisième loi explique les fusées : elles éjectent des gaz vers l'arrière, et les gaz poussent la fusée vers l'avant. "
            "Pas besoin d'air pour « s'appuyer » : c'est pour ça qu'elles fonctionnent dans l'espace.",
            "On mesure les forces en newtons (N) : 1 N, c'est à peu près le poids d'une pomme de 100 g. Les frottements sont des forces "
            "qui s'opposent au glissement ; sans eux, impossible de marcher ou de freiner.",
        ],
        'expert': [
            "Le principe fondamental de la dynamique s'écrit en toute généralité ΣF⃗ = dp⃗/dt, avec la quantité de mouvement p⃗ = m v⃗ ; "
            "pour une masse constante, ΣF⃗ = m a⃗. Il n'est valable que dans un référentiel galiléen (inertiel) : dans un référentiel "
            "accéléré ou en rotation apparaissent des forces d'inertie (centrifuge, Coriolis).",
            "En l'absence de force extérieure, la quantité de mouvement totale se conserve : c'est la base du calcul des chocs et de la "
            "propulsion. Pour une fusée, l'équation de Tsiolkovski donne Δv = v_e ln(m₀ / m_f).",
            "La mécanique newtonienne est une approximation : elle cesse d'être exacte aux vitesses proches de celle de la lumière "
            "(relativité restreinte, p = γ m v) et à l'échelle atomique (mécanique quantique). Pour le frottement solide, le modèle de "
            "Coulomb donne F ≤ μ N, avec μ ≈ 0,7 à 0,9 pour un pneu sur route sèche.",
        ],
        'formulas': [
            {'f': 'ΣF = m · a', 'l': 'deuxième loi de Newton (N, kg, m/s²)'},
            {'f': 'p = m · v', 'l': 'quantité de mouvement'},
            {'f': 'F_A→B = − F_B→A', 'l': 'action-réaction'},
            {'f': 'Δv = v_e · ln(m₀ / m_f)', 'l': 'équation de la fusée (Tsiolkovski)'},
        ],
        'numbers': [
            {'v': '1 N', 'l': 'à peu près le poids d\'une pomme de 100 g'},
            {'v': '≈ 0,9 g', 'l': 'accélération d\'une voiture qui passe de 0 à 100 km/h en 3 s'},
            {'v': 'μ ≈ 0,7 à 0,9', 'l': 'adhérence d\'un pneu sur route sèche'},
        ],
        'exp': {
            'title': 'La pièce qui tombe pile',
            'steps': [
                "Pose une carte à jouer sur un gobelet en plastique, puis une pièce de monnaie au centre de la carte.",
                "D'une pichenette rapide et horizontale, chasse la carte.",
                "La carte part, la pièce tombe dans le gobelet : rien ne l'a poussée sur le côté, elle garde son immobilité. C'est l'inertie.",
            ],
            'safety': 'Prends un gobelet en plastique, pas un verre.',
        },
        'svg': svg_forces(),
        'caption': "Le poids et la réaction du sol se compensent ; la poussée est plus forte que les frottements : "
                   "la force qui reste fait accélérer le bloc.",
        'related': ['gravitation', 'energie'],
    },
    {
        'id': 'gravitation', 'domain': 'physique', 'title': 'La gravitation',
        'tagline': 'La force qui fait tomber les pommes et tourner la Lune',
        'kid': [
            "Tous les objets qui ont une masse s'attirent : c'est la gravitation. Elle est minuscule entre deux petits objets, mais "
            "énorme quand l'un des deux est une planète : c'est elle qui nous garde sur le sol et fait tomber ce qu'on lâche.",
            "La gravitation agit aussi très loin : elle retient la Lune autour de la Terre et la Terre autour du Soleil. La Lune « tombe » "
            "en permanence vers la Terre, mais elle file si vite sur le côté qu'elle la rate à chaque fois : c'est ça, une orbite.",
            "Sur la Lune, la pesanteur est six fois plus faible que sur Terre : les astronautes y font des bonds bien plus grands, "
            "même avec leur lourde combinaison.",
        ],
        'dyk': "Sans air, une plume et un marteau tombent exactement à la même vitesse. L'astronaute David Scott l'a montré sur la Lune "
               "en 1971, pendant la mission Apollo 15.",
        'more': [
            "Isaac Newton a compris en 1687 que la force qui fait tomber une pomme est la même que celle qui retient la Lune. "
            "Elle augmente avec les masses et diminue vite avec la distance : deux fois plus loin, l'attraction est quatre fois plus faible.",
            "Le poids d'un objet, c'est la force avec laquelle la planète l'attire : P = m × g, avec g ≈ 9,8 N/kg sur Terre. La masse "
            "(en kg) est la même partout, le poids change : un objet de 60 kg pèse environ 590 N sur Terre, et 97 N sur la Lune.",
            "La gravitation explique aussi les marées : la Lune attire un peu plus fort l'océan du côté qui lui fait face que le centre "
            "de la Terre, et un peu moins celui du côté opposé. Cela crée deux renflements d'eau qui font le tour de la planète.",
        ],
        'expert': [
            "Loi de Newton : F = G m₁ m₂ / r², avec G = 6,674 × 10⁻¹¹ N·m²·kg⁻². C'est de loin la plus faible des quatre interactions "
            "fondamentales : entre deux protons, l'attraction gravitationnelle est environ 10³⁶ fois plus faible que la répulsion électrique.",
            "Vitesse de satellisation en orbite basse ≈ 7,8 km/s ; vitesse de libération terrestre v = √(2GM/R) ≈ 11,2 km/s. "
            "Troisième loi de Kepler, pour une orbite circulaire : T² = 4π² r³ / (G M).",
            "La relativité générale d'Einstein (1915) remplace la force par une courbure de l'espace-temps. Elle explique l'avance du "
            "périhélie de Mercure (43″ par siècle) et la déviation de la lumière. Le GPS doit en tenir compte : sans correction, les "
            "horloges des satellites dériveraient d'environ 38 µs par jour, soit environ 10 km d'erreur de position par jour.",
        ],
        'formulas': [
            {'f': 'F = G · m₁ · m₂ / r²', 'l': 'gravitation universelle'},
            {'f': 'P = m · g', 'l': 'poids (N) = masse (kg) × pesanteur (N/kg)'},
            {'f': 'v_lib = √(2 G M / R)', 'l': 'vitesse de libération'},
            {'f': 'T² = 4π² r³ / (G M)', 'l': 'troisième loi de Kepler'},
        ],
        'numbers': [
            {'v': 'g = 9,81 m/s²', 'l': 'pesanteur à la surface de la Terre'},
            {'v': '1,62 m/s²', 'l': 'pesanteur sur la Lune'},
            {'v': '11,2 km/s', 'l': 'vitesse pour échapper à la Terre'},
        ],
        'exp': {
            'title': 'La feuille et le livre',
            'steps': [
                "Lâche en même temps, de la même hauteur, un livre et une feuille de papier tenue à plat : le livre arrive en premier.",
                "Pose maintenant la feuille à plat sur le livre, et lâche le tout.",
                "Ils tombent ensemble ! Ce n'est pas la légèreté qui ralentissait la feuille, mais l'air : le livre lui ouvre le chemin.",
            ],
            'safety': '',
        },
        'svg': svg_gravitation(),
        'caption': "La Lune est attirée vers la Terre comme la pomme, mais sa vitesse sur le côté la fait tourner autour au lieu de tomber dessus.",
        'related': ['forces-mouvement', 'energie', 'lumiere'],
    },
    {
        'id': 'chaleur-temperature', 'domain': 'physique', 'title': 'Chaleur et température',
        'tagline': "L'agitation invisible de la matière",
        'kid': [
            "La température dit à quel point les particules d'un objet s'agitent : plus elles bougent vite, plus l'objet est chaud. "
            "Le thermomètre la mesure en degrés Celsius.",
            "La chaleur, c'est de l'énergie qui passe toujours de l'objet chaud vers l'objet froid, jusqu'à ce qu'ils soient à la même "
            "température. Ton chocolat chaud refroidit parce qu'il donne sa chaleur à l'air de la pièce.",
            "La chaleur voyage de trois façons : par contact (la cuillère qui chauffe dans le chocolat), par le mouvement d'un liquide ou "
            "d'un gaz (l'air chaud qui monte au-dessus d'un radiateur) et par rayonnement (la chaleur du Soleil, qui traverse le vide de l'espace).",
        ],
        'dyk': "Il existe une température la plus basse possible, le zéro absolu : −273,15 °C. On ne peut jamais l'atteindre tout à fait, "
               "mais des laboratoires s'en approchent à quelques milliardièmes de degré.",
        'more': [
            "Le carrelage paraît plus froid que le tapis, alors qu'ils sont à la même température : le carrelage conduit mieux la chaleur "
            "et l'enlève plus vite à ton pied. Notre peau sent surtout les échanges de chaleur, pas vraiment la température.",
            "Les scientifiques utilisent le kelvin (K) : 0 K est le zéro absolu, et 1 K d'écart vaut 1 °C d'écart. Ainsi 20 °C = 293,15 K.",
            "Il faut plus ou moins d'énergie pour réchauffer chaque matière. L'eau est championne : il faut environ 4 200 joules pour "
            "chauffer un litre d'eau d'un seul degré. C'est pour ça que les océans adoucissent le climat des côtes.",
        ],
        'expert': [
            "La température thermodynamique est liée à l'énergie cinétique moyenne d'agitation : pour un gaz parfait monoatomique, "
            "⟨Ec⟩ = 3/2 k_B T, avec k_B = 1,381 × 10⁻²³ J/K. Sans changement d'état, la chaleur échangée vaut Q = m c ΔT "
            "(eau liquide : c ≈ 4 186 J·kg⁻¹·K⁻¹).",
            "Conduction : loi de Fourier, φ⃗ = −λ ∇T (λ ≈ 400 W·m⁻¹·K⁻¹ pour le cuivre, 0,6 pour l'eau, 0,026 pour l'air immobile, "
            "d'où l'efficacité des isolants qui emprisonnent de l'air). Convection : φ = h S ΔT. Rayonnement : loi de Stefan-Boltzmann, "
            "P = ε σ S T⁴, avec σ = 5,670 × 10⁻⁸ W·m⁻²·K⁻⁴.",
            "Le spectre du rayonnement thermique a un maximum donné par la loi de Wien : λ_max ≈ 2 898 µm·K / T. Le Soleil (≈ 5 800 K) "
            "émet surtout dans le visible ; le corps humain (≈ 310 K) vers 9 à 10 µm, dans l'infrarouge, ce que voient les caméras thermiques.",
        ],
        'formulas': [
            {'f': 'Q = m · c · ΔT', 'l': 'chaleur pour chauffer sans changer d\'état'},
            {'f': 'T (K) = θ (°C) + 273,15', 'l': 'kelvins et degrés Celsius'},
            {'f': 'P = ε · σ · S · T⁴', 'l': 'rayonnement (Stefan-Boltzmann)'},
            {'f': 'λ_max · T ≈ 2 898 µm·K', 'l': 'loi de Wien'},
        ],
        'numbers': [
            {'v': '−273,15 °C', 'l': 'zéro absolu (0 K)'},
            {'v': '4 186 J/(kg·K)', 'l': 'capacité thermique de l\'eau'},
            {'v': '37 °C ≈ 310 K', 'l': 'température du corps humain'},
        ],
        'exp': {
            'title': 'Le métal « froid »',
            'steps': [
                "Dans une même pièce, pose une main sur un objet en métal et l'autre sur un objet en bois.",
                "Le métal semble plus froid… alors que les deux sont à la même température !",
                "Le métal emporte simplement plus vite la chaleur de ta main : c'est un bon conducteur thermique.",
            ],
            'safety': '',
        },
        'svg': svg_chaleur(),
        'caption': "Conduction : la chaleur avance de proche en proche dans un solide. Convection : un liquide ou un gaz chauffé circule. "
                   "Rayonnement : la chaleur voyage comme la lumière, même dans le vide.",
        'related': ['energie', 'etats-matiere', 'lumiere'],
    },
    {
        'id': 'etats-matiere', 'domain': 'physique', 'title': 'Les états de la matière',
        'tagline': 'Solide, liquide, gaz… et plasma',
        'kid': [
            "La matière peut être solide, liquide ou gazeuse. L'eau le montre bien : glaçon, eau du robinet, vapeur. C'est la même eau, "
            "seulement ses petites particules ne bougent pas de la même façon.",
            "Dans un solide, les particules sont serrées et vibrent sur place : le solide garde sa forme. Dans un liquide, elles restent "
            "proches mais glissent les unes sur les autres : le liquide coule et prend la forme du récipient. Dans un gaz, elles sont très "
            "éloignées et filent dans tous les sens : le gaz occupe toute la place.",
            "Quand on chauffe, les particules s'agitent davantage : le glaçon fond, puis l'eau s'évapore. Quand on refroidit, c'est l'inverse : "
            "la vapeur se condense en gouttes, l'eau gèle.",
        ],
        'dyk': "Il existe un quatrième état, le plasma : un gaz si chaud que ses atomes perdent des électrons. Les étoiles, les éclairs et les "
               "aurores boréales sont faits de plasma. C'est même l'état le plus répandu de la matière visible dans l'Univers.",
        'more': [
            "Les changements d'état ont des noms : fusion (solide → liquide), solidification (liquide → solide), vaporisation "
            "(liquide → gaz), liquéfaction ou condensation (gaz → liquide), sublimation (solide → gaz directement, comme la glace "
            "carbonique) et condensation solide (gaz → solide, comme le givre).",
            "Pendant qu'un corps pur change d'état, sa température reste constante : la glace qui fond reste à 0 °C tant qu'il en reste. "
            "L'énergie apportée sert à défaire les liens entre les particules au lieu de les agiter davantage.",
            "La température d'ébullition dépend de la pression : en altitude, l'eau bout en dessous de 100 °C (vers 85 °C au sommet du "
            "mont Blanc). C'est l'inverse dans une cocotte-minute, où l'eau bout vers 120 °C et cuit les aliments plus vite.",
        ],
        'expert': [
            "Le diagramme de phases (P, T) d'un corps pur sépare les domaines solide, liquide et gaz par des courbes d'équilibre. Elles se "
            "rejoignent au point triple (eau : 273,16 K et 611,657 Pa) ; la courbe liquide-gaz s'arrête au point critique (eau : 647,1 K et "
            "22,064 MPa), au-delà duquel on parle de fluide supercritique.",
            "L'énergie d'un changement d'état est la chaleur latente : pour l'eau, L_fusion ≈ 334 kJ/kg et L_vaporisation ≈ 2 257 kJ/kg "
            "à 100 °C, près de sept fois plus. La pente des courbes d'équilibre suit la relation de Clapeyron, dP/dT = L / (T Δv). L'eau est "
            "une exception : sa courbe solide-liquide a une pente négative, car la glace est moins dense que l'eau liquide.",
            "Pour un gaz parfait, P V = n R T, avec R = 8,314 J·mol⁻¹·K⁻¹ : une mole occupe environ 22,4 L à 0 °C et 1 atm (24,5 L à 25 °C). "
            "Les gaz réels s'en écartent à haute pression et basse température (équation de van der Waals).",
        ],
        'formulas': [
            {'f': 'P · V = n · R · T', 'l': 'gaz parfait (Pa, m³, mol, K)'},
            {'f': 'Q = m · L', 'l': 'chaleur d\'un changement d\'état'},
            {'f': 'dP/dT = L / (T · Δv)', 'l': 'relation de Clapeyron'},
        ],
        'numbers': [
            {'v': '0 °C et 100 °C', 'l': 'fusion de la glace et ébullition de l\'eau, à 1 atm'},
            {'v': '2 257 kJ/kg', 'l': 'énergie pour vaporiser l\'eau à 100 °C'},
            {'v': '≈ 85 °C', 'l': 'ébullition de l\'eau au sommet du mont Blanc'},
        ],
        'exp': {
            'title': 'La bouteille qui « transpire »',
            'steps': [
                "Sors une bouteille bien fraîche du réfrigérateur et pose-la sur la table.",
                "Attends quelques minutes : des gouttelettes apparaissent sur la paroi.",
                "Elles ne viennent pas de l'intérieur : c'est la vapeur d'eau invisible de l'air qui se condense au contact du froid.",
            ],
            'safety': '',
        },
        'svg': svg_etats(),
        'caption': "En chauffant, on passe de gauche à droite ; en refroidissant, de droite à gauche. Seule l'agitation des particules change.",
        'related': ['chaleur-temperature', 'atome', 'energie'],
    },
    {
        'id': 'electricite', 'domain': 'physique', 'title': "L'électricité",
        'tagline': 'Des charges en mouvement qui font tourner le monde moderne',
        'kid': [
            "L'électricité, c'est le mouvement de toutes petites particules chargées, les électrons, dans un fil de métal. Pour qu'elles "
            "circulent, il faut un circuit fermé : une boucle sans interruption, de la pile à la lampe et retour.",
            "La pile ou la prise jouent le rôle d'une pompe : elles poussent les électrons. Les métaux laissent passer le courant "
            "(ce sont des conducteurs) ; le plastique ou le bois l'arrêtent (ce sont des isolants). C'est pour ça que les fils sont "
            "entourés de plastique.",
            "Attention : l'électricité de la maison est dangereuse. On ne touche jamais une prise ou un appareil branché avec les mains mouillées.",
        ],
        'dyk': "Dans un fil, les électrons avancent très lentement, souvent moins d'un millimètre par seconde ! Pourtant la lampe s'allume tout "
               "de suite : la « poussée » se transmet presque à la vitesse de la lumière, comme dans un tuyau déjà plein de billes.",
        'more': [
            "Trois grandeurs décrivent un circuit : la tension (en volts, V), qui est la « poussée » ; l'intensité du courant "
            "(en ampères, A), qui est le débit de charges ; la résistance (en ohms, Ω), qui freine le courant. Elles sont liées par la "
            "loi d'Ohm : U = R × I.",
            "La puissance électrique, en watts, vaut P = U × I. En France, les prises délivrent une tension alternative de 230 V qui "
            "oscille 50 fois par seconde (50 Hz).",
            "Un courant qui traverse une résistance la chauffe : c'est l'effet Joule, utilisé dans les grille-pain et les radiateurs, "
            "mais qui fait aussi perdre de l'énergie dans les câbles.",
        ],
        'expert': [
            "Charge élémentaire e = 1,602 × 10⁻¹⁹ C ; 1 A = 1 C/s, soit environ 6,24 × 10¹⁸ électrons par seconde. Lois de Kirchhoff : "
            "la somme des courants arrivant à un nœud est nulle (conservation de la charge), la somme des tensions le long d'une maille "
            "aussi (conservation de l'énergie).",
            "Résistance d'un fil : R = ρ L / S (cuivre : ρ ≈ 1,7 × 10⁻⁸ Ω·m). Pertes par effet Joule : P = R I². C'est pourquoi on transporte "
            "l'électricité sous très haute tension (jusqu'à 400 kV en France) : à puissance égale, le courant est plus faible et les "
            "pertes, proportionnelles à I², chutent fortement.",
            "En régime sinusoïdal, la tension efficace vaut U_eff = U_max / √2 : 230 V efficaces correspondent à environ 325 V crête. "
            "Les dipôles se décrivent par une impédance complexe Z (R, jLω, 1/(jCω)) ; la puissance active vaut P = U_eff I_eff cos φ.",
        ],
        'formulas': [
            {'f': 'U = R · I', 'l': 'loi d\'Ohm (V, Ω, A)'},
            {'f': 'P = U · I = R · I²', 'l': 'puissance et effet Joule'},
            {'f': 'R = ρ · L / S', 'l': 'résistance d\'un fil'},
            {'f': 'U_eff = U_max / √2', 'l': 'tension efficace (sinusoïdale)'},
        ],
        'numbers': [
            {'v': '230 V · 50 Hz', 'l': 'les prises en France'},
            {'v': '6,24 × 10¹⁸', 'l': 'électrons par seconde dans 1 A'},
            {'v': '400 kV', 'l': 'lignes à très haute tension'},
        ],
        'exp': {
            'title': 'Le ballon magique',
            'steps': [
                "Gonfle un ballon et frotte-le une dizaine de fois sur des cheveux propres et secs.",
                "Approche-le de petits morceaux de papier : ils sautent vers le ballon !",
                "En frottant, des électrons sont passés de tes cheveux au ballon : il est chargé, c'est de l'électricité statique.",
            ],
            'safety': 'Ne fais jamais d\'expérience avec les prises de la maison.',
        },
        'svg': svg_electricite(),
        'caption': "Par convention, le courant va de la borne + vers la borne − dans le circuit ; les électrons, eux, circulent dans l'autre sens.",
        'related': ['atome', 'energie'],
    },
    {
        'id': 'ondes-son', 'domain': 'physique', 'title': 'Le son et les ondes',
        'tagline': 'Des vibrations qui voyagent',
        'kid': [
            "Le son est une vibration. Quand tu parles, tes cordes vocales vibrent et poussent l'air, qui pousse l'air d'à côté, et ainsi de "
            "suite jusqu'à l'oreille de ton ami. L'air, lui, ne voyage pas : c'est la vibration qui se transmet, comme une « ola » dans un stade.",
            "Le son a besoin de matière pour avancer. Dans l'espace, où il n'y a pas d'air, les explosions des films devraient être silencieuses !",
            "Un son aigu correspond à une vibration rapide, un son grave à une vibration lente. Un son fort fait vibrer l'air plus énergiquement.",
        ],
        'dyk': "Pendant un orage, compte les secondes entre l'éclair et le tonnerre, puis divise par trois : tu obtiens à peu près la distance "
               "de l'orage en kilomètres. La lumière arrive presque tout de suite ; le son, lui, met environ trois secondes par kilomètre.",
        'more': [
            "La vitesse du son dépend du milieu : environ 340 m/s dans l'air, 1 500 m/s dans l'eau et près de 6 000 m/s dans l'acier. "
            "Certaines baleines communiquent ainsi sur des centaines de kilomètres.",
            "La hauteur d'un son se mesure par sa fréquence, en hertz (Hz) : le nombre de vibrations par seconde. L'oreille humaine "
            "entend à peu près de 20 Hz à 20 000 Hz. Au-dessus, ce sont les ultrasons (chauves-souris, échographie) ; en dessous, "
            "les infrasons (éléphants, séismes).",
            "Le niveau sonore se mesure en décibels (dB). L'échelle n'est pas ordinaire : +10 dB correspondent à une intensité dix fois "
            "plus grande. Au-delà d'environ 85 dB pendant longtemps, l'oreille peut être abîmée.",
        ],
        'expert': [
            "Une onde transporte de l'énergie sans transporter de matière. Relation fondamentale : v = λ f. Dans un fluide, le son est une "
            "onde longitudinale de pression ; dans un gaz parfait, v = √(γ R T / M), soit ≈ 343 m/s dans l'air à 20 °C (γ = 1,4 ; M = 29 g/mol).",
            "Niveau d'intensité : L = 10 log₁₀(I / I₀), avec I₀ = 10⁻¹² W/m² (seuil d'audition à 1 kHz). Effet Doppler pour une source "
            "qui s'approche : f' = f · v / (v − v_s), d'où le changement de note d'une sirène qui passe, utilisé aussi par les radars et "
            "en astronomie.",
            "Toutes les ondes, sonores, lumineuses ou à la surface de l'eau, partagent les mêmes propriétés : réflexion, réfraction, "
            "diffraction, interférences (principe des casques antibruit actifs) et résonance (cordes, tuyaux, ponts).",
        ],
        'formulas': [
            {'f': 'v = λ · f', 'l': 'vitesse = longueur d\'onde × fréquence'},
            {'f': 'L = 10 · log₁₀(I / I₀)', 'l': 'niveau sonore en décibels'},
            {'f': 'f\' = f · v / (v − v_s)', 'l': 'effet Doppler, source qui s\'approche'},
        ],
        'numbers': [
            {'v': '343 m/s', 'l': 'vitesse du son dans l\'air à 20 °C'},
            {'v': '≈ 1 480 m/s', 'l': 'vitesse du son dans l\'eau'},
            {'v': '20 Hz – 20 kHz', 'l': 'ce que l\'oreille humaine entend'},
        ],
        'exp': {
            'title': 'Le téléphone à ficelle',
            'steps': [
                "Perce le fond de deux pots de yaourt vides et relie-les par une longue ficelle, bloquée par un nœud de chaque côté.",
                "Éloigne-toi jusqu'à ce que la ficelle soit bien tendue. Parle dans un pot pendant qu'un ami écoute dans l'autre.",
                "Ta voix fait vibrer le fond du pot, puis la ficelle, puis l'autre pot : le son voyage mieux dans la ficelle tendue que dans l'air.",
            ],
            'safety': 'Demande à un adulte de percer les pots.',
        },
        'svg': svg_son(),
        'caption': "Le haut-parleur pousse et tire l'air : des zones comprimées et détendues se succèdent. La distance entre deux compressions "
                   "est la longueur d'onde.",
        'related': ['lumiere', 'energie'],
    },
    {
        'id': 'lumiere', 'domain': 'physique', 'title': 'La lumière',
        'tagline': "Une onde, des grains d'énergie, et toutes les couleurs",
        'kid': [
            "La lumière voyage incroyablement vite : environ 300 000 kilomètres par seconde. Elle pourrait faire plus de sept fois le tour "
            "de la Terre en une seconde. Celle du Soleil met quand même 8 minutes à nous parvenir.",
            "La lumière blanche du Soleil est en réalité un mélange de toutes les couleurs. Un prisme, ou les gouttes de pluie, peuvent "
            "les séparer : c'est l'arc-en-ciel.",
            "Nous voyons un objet parce qu'il renvoie de la lumière vers nos yeux. Une pomme est rouge parce qu'elle renvoie surtout la "
            "lumière rouge et absorbe les autres couleurs.",
        ],
        'dyk': "Quand tu regardes les étoiles, tu regardes le passé : la lumière de certaines étoiles a voyagé des centaines ou des milliers "
               "d'années avant d'arriver dans ton œil.",
        'more': [
            "La lumière est une onde électromagnétique. Ce qui distingue les couleurs, c'est la longueur d'onde : environ 400 nanomètres "
            "pour le violet, 700 pour le rouge. Au-delà du visible, il y a d'un côté l'infrarouge, les micro-ondes et les ondes radio, de "
            "l'autre l'ultraviolet, les rayons X et les rayons gamma : c'est la même famille.",
            "Quand la lumière passe d'un milieu à un autre (air, eau, verre), elle change de vitesse et se courbe : c'est la réfraction. "
            "C'est pourquoi une paille paraît cassée dans un verre d'eau, et c'est ainsi que fonctionnent les lunettes et les loupes.",
            "La lumière se comporte aussi comme un flot de petits grains d'énergie, les photons. Cette double nature, onde et particule, "
            "est l'une des grandes découvertes du XXᵉ siècle.",
        ],
        'expert': [
            "c = 299 792 458 m/s exactement (valeur fixée en 1983 pour définir le mètre). Dans un milieu d'indice n, la vitesse vaut c/n "
            "(eau : n ≈ 1,33 ; verre : ≈ 1,5). Loi de Snell-Descartes : n₁ sin θ₁ = n₂ sin θ₂ ; au-delà de l'angle critique, la réflexion "
            "est totale, principe de la fibre optique.",
            "Énergie d'un photon : E = h ν = h c / λ, avec h = 6,626 × 10⁻³⁴ J·s ; un photon vert (λ ≈ 530 nm) transporte environ 2,3 eV. "
            "L'effet photoélectrique, expliqué par Einstein en 1905 (prix Nobel 1921), montre que la lumière échange son énergie par quanta.",
            "Les équations de Maxwell (1865) décrivent la lumière comme une onde de champs électrique et magnétique couplés, avec "
            "c = 1/√(μ₀ ε₀). La dispersion (n dépend de λ) explique la décomposition par un prisme ; la diffraction limite la "
            "résolution d'un instrument d'ouverture D : θ ≈ 1,22 λ / D.",
        ],
        'formulas': [
            {'f': 'c = λ · ν', 'l': 'vitesse = longueur d\'onde × fréquence'},
            {'f': 'E = h · ν', 'l': 'énergie d\'un photon'},
            {'f': 'n₁ · sin θ₁ = n₂ · sin θ₂', 'l': 'réfraction (Snell-Descartes)'},
            {'f': 'θ ≈ 1,22 · λ / D', 'l': 'limite de résolution d\'un instrument'},
        ],
        'numbers': [
            {'v': '299 792 km/s', 'l': 'vitesse de la lumière dans le vide'},
            {'v': '400 – 700 nm', 'l': 'longueurs d\'onde visibles, du violet au rouge'},
            {'v': '8 min 20 s', 'l': 'trajet de la lumière du Soleil jusqu\'à la Terre'},
        ],
        'exp': {
            'title': 'Un arc-en-ciel sur ta table',
            'steps': [
                "Remplis un verre d'eau à ras bord et pose-le au bord d'une fenêtre ensoleillée, au-dessus d'une feuille blanche posée au sol.",
                "Déplace la feuille jusqu'à voir apparaître des bandes de couleurs.",
                "L'eau dévie chaque couleur un peu différemment : la lumière blanche se sépare, comme dans un prisme.",
            ],
            'safety': 'Ne regarde jamais le Soleil directement.',
        },
        'svg': svg_lumiere(),
        'caption': "Le verre ralentit davantage le violet que le rouge : chaque couleur est déviée différemment, et la lumière blanche s'étale en spectre.",
        'related': ['ondes-son', 'atome', 'chaleur-temperature'],
    },
    # ---------------------------------------------------------------- CHIMIE
    {
        'id': 'atome', 'domain': 'chimie', 'title': "L'atome",
        'tagline': 'La brique de base de toute la matière',
        'kid': [
            "Tout ce qui t'entoure, ton bureau, l'air, l'eau, toi-même, est fait de minuscules briques appelées atomes. Ils sont si petits "
            "qu'il en faudrait environ dix millions alignés pour faire un millimètre.",
            "Au centre de chaque atome, il y a un noyau fait de protons et de neutrons. Autour, des électrons, encore bien plus légers, "
            "bougent si vite qu'on ne peut pas dire exactement où ils sont : ils forment comme un nuage.",
            "Il existe un peu plus d'une centaine de sortes d'atomes, qu'on appelle des éléments : l'hydrogène, le carbone, l'oxygène, "
            "le fer, l'or… En les assemblant, la nature fabrique tout le reste, un peu comme avec des briques de construction.",
        ],
        'dyk': "Si le noyau d'un atome avait la taille d'un grain de sable posé au centre d'un stade de foot, ses électrons se trouveraient "
               "au niveau des tribunes. Un atome, c'est donc presque entièrement du vide !",
        'more': [
            "Le noyau contient deux sortes de particules : les protons, qui ont une charge électrique positive, et les neutrons, sans charge. "
            "Les électrons, eux, sont négatifs. Comme un atome a autant d'électrons que de protons, il est électriquement neutre.",
            "C'est le nombre de protons qui donne son identité à un élément : 1 pour l'hydrogène, 6 pour le carbone, 8 pour l'oxygène, "
            "79 pour l'or. C'est le numéro atomique. Deux atomes du même élément peuvent avoir un nombre de neutrons différent : ce sont "
            "des isotopes, comme le carbone 12 et le carbone 14, qui sert à dater les objets anciens.",
            "Les électrons se rangent par couches autour du noyau. Ceux de la couche la plus extérieure décident de la façon dont l'atome "
            "s'associe avec d'autres : c'est toute la chimie.",
        ],
        'expert': [
            "Ordres de grandeur : rayon atomique ≈ 30 à 300 pm ; rayon nucléaire ≈ 1 à 8 fm (r ≈ 1,2 fm × A^(1/3)). Le noyau concentre plus "
            "de 99,9 % de la masse : m_p ≈ 1,673 × 10⁻²⁷ kg, m_n ≈ 1,675 × 10⁻²⁷ kg, m_e ≈ 9,109 × 10⁻³¹ kg (m_p / m_e ≈ 1 836).",
            "Le modèle planétaire de Bohr (1913) est dépassé : en mécanique quantique, chaque électron est décrit par une fonction d'onde, "
            "et l'on parle d'orbitales (s, p, d, f) caractérisées par les nombres quantiques n, l, m_l et m_s. Le principe d'exclusion de "
            "Pauli et la règle de Klechkowski expliquent le remplissage des couches, donc la structure du tableau périodique.",
            "La cohésion du noyau vient de l'interaction forte, qui l'emporte sur la répulsion électrique entre protons à très courte "
            "distance (≈ 1 fm). L'énergie de liaison par nucléon culmine vers le fer et le nickel (≈ 8,8 MeV) : c'est pourquoi la fusion "
            "des noyaux légers et la fission des noyaux lourds libèrent de l'énergie.",
        ],
        'formulas': [
            {'f': 'A = Z + N', 'l': 'nombre de masse = protons + neutrons'},
            {'f': 'r ≈ 1,2 fm · A^(1/3)', 'l': 'rayon d\'un noyau'},
            {'f': 'N_A = 6,022 × 10²³ mol⁻¹', 'l': 'nombre d\'entités dans une mole (Avogadro)'},
        ],
        'numbers': [
            {'v': '≈ 0,1 nm', 'l': 'taille typique d\'un atome'},
            {'v': '≈ 100 000', 'l': 'fois plus grand que son noyau'},
            {'v': '118', 'l': 'éléments connus aujourd\'hui'},
        ],
        'exp': None,
        'svg': svg_atome(),
        'caption': "Schéma simplifié : en réalité, les électrons forment un nuage autour du noyau, et le noyau est environ 100 000 fois plus petit que l'atome.",
        'related': ['molecules', 'etats-matiere', 'electricite', 'lumiere'],
    },
    {
        'id': 'molecules', 'domain': 'chimie', 'title': 'Molécules et liaisons',
        'tagline': "Comment les atomes s'assemblent",
        'kid': [
            "Les atomes aiment s'associer. Quand plusieurs atomes s'accrochent ensemble, ils forment une molécule. Une molécule d'eau, "
            "par exemple, c'est un atome d'oxygène accroché à deux atomes d'hydrogène : H₂O.",
            "Ces « crochets » s'appellent des liaisons chimiques. Les atomes mettent en commun certains de leurs électrons, un peu comme "
            "deux enfants qui se tiennent par la main.",
            "En changeant les atomes et leur façon de s'assembler, on obtient des millions de substances différentes : le sucre, le "
            "plastique, l'ADN, les médicaments…",
        ],
        'dyk': "Une seule goutte d'eau contient environ 1,7 × 10²¹ molécules, soit mille sept cents milliards de milliards. "
               "C'est des centaines de milliards de fois plus que le nombre d'humains sur Terre.",
        'more': [
            "Dans une liaison covalente, deux atomes partagent une paire d'électrons (eau, sucre, ADN). Dans une liaison ionique, un atome "
            "cède un électron à un autre : on obtient deux ions de charges opposées qui s'attirent, comme dans le sel de cuisine "
            "(Na⁺ et Cl⁻). Dans les métaux, les électrons sont partagés par tout le métal, ce qui explique qu'ils conduisent l'électricité.",
            "Entre les molécules existent des attractions plus faibles. Les liaisons hydrogène entre molécules d'eau expliquent que l'eau "
            "soit liquide à température ambiante, alors qu'une molécule aussi petite devrait être un gaz. Ce sont aussi elles qui tiennent "
            "ensemble les deux brins de l'ADN.",
            "La forme d'une molécule compte autant que sa composition : la molécule d'eau est coudée, ce qui la rend « polaire » (un côté "
            "légèrement négatif, l'autre positif). C'est pour ça que l'eau dissout si bien le sel et le sucre.",
        ],
        'expert': [
            "La règle de l'octet (Lewis, 1916) prévoit que les atomes des deux premières périodes tendent à s'entourer de huit électrons "
            "de valence. La théorie VSEPR prédit la géométrie : l'eau est coudée (angle H–O–H ≈ 104,5°) à cause de ses deux doublets non "
            "liants ; le méthane est tétraédrique (109,5°).",
            "Énergies de liaison typiques : C–H ≈ 410 kJ/mol, O–H ≈ 460 kJ/mol, triple liaison N≡N ≈ 945 kJ/mol ; liaison hydrogène "
            "≈ 5 à 30 kJ/mol ; interactions de van der Waals ≈ 0,5 à 5 kJ/mol. Une liaison est polarisée quand la différence "
            "d'électronégativité (échelle de Pauling) entre ses atomes est grande ; au-delà d'environ 1,7, on la considère surtout ionique.",
            "La mécanique quantique décrit les liaisons par recouvrement d'orbitales (orbitales moléculaires, hybridation sp, sp², sp³). "
            "La stéréochimie compte : deux molécules images l'une de l'autre dans un miroir (énantiomères) peuvent avoir des effets "
            "biologiques très différents, ce qui est crucial pour les médicaments.",
        ],
        'formulas': [
            {'f': 'n = m / M', 'l': 'quantité de matière (mol) = masse / masse molaire'},
            {'f': 'N = n · N_A', 'l': 'nombre de molécules'},
            {'f': 'H–O–H ≈ 104,5°', 'l': 'angle de la molécule d\'eau'},
        ],
        'numbers': [
            {'v': '18 g/mol', 'l': 'masse molaire de l\'eau'},
            {'v': '≈ 460 kJ/mol', 'l': 'énergie d\'une liaison O–H'},
            {'v': '1,7 × 10²¹', 'l': 'molécules dans une goutte d\'eau'},
        ],
        'exp': {
            'title': 'Le poivre qui s\'enfuit',
            'steps': [
                "Verse de l'eau dans une assiette et saupoudre du poivre à la surface.",
                "Trempe le bout de ton doigt dans du liquide vaisselle, puis touche le centre de l'eau.",
                "Le poivre file vers les bords ! Le savon casse la « peau » de l'eau, formée par les liaisons entre ses molécules : "
                "c'est la tension superficielle.",
            ],
            'safety': 'Lave-toi les mains après.',
        },
        'svg': svg_molecules(),
        'caption': "Dans l'eau, l'oxygène attire davantage les électrons : il porte une légère charge négative (δ−) et les hydrogènes une légère "
                   "charge positive (δ+). Les molécules voisines s'attirent : ce sont les liaisons hydrogène.",
        'related': ['atome', 'reaction-chimique', 'acides-bases'],
    },
    {
        'id': 'reaction-chimique', 'domain': 'chimie', 'title': 'La réaction chimique',
        'tagline': 'Rien ne se perd, tout se transforme',
        'kid': [
            "Une réaction chimique transforme des substances en d'autres substances. Quand le bois brûle, quand le fer rouille, quand un "
            "gâteau cuit ou quand tu digères, des réactions chimiques ont lieu.",
            "Pendant une réaction, les atomes ne disparaissent pas : ils se séparent et se réassemblent autrement, comme des briques de "
            "construction qu'on démonte pour fabriquer autre chose.",
            "Certaines réactions dégagent de la chaleur, comme un feu de bois. D'autres ont besoin d'énergie pour se faire, comme la "
            "photosynthèse des plantes, qui utilise celle de la lumière.",
        ],
        'dyk': "Au XVIIIᵉ siècle, Antoine Lavoisier pesait avec soin ce qu'il y avait avant et après ses réactions, dans des récipients fermés : "
               "la masse totale ne change jamais. On résume souvent sa découverte par la phrase « Rien ne se perd, rien ne se crée, tout se transforme ».",
        'more': [
            "On écrit une réaction sous forme d'équation. Pour la combustion du gaz de cuisine (le méthane) : CH₄ + 2 O₂ → CO₂ + 2 H₂O. "
            "Il y a autant d'atomes de chaque sorte à gauche et à droite : 1 carbone, 4 hydrogènes et 4 oxygènes.",
            "Pour démarrer, la plupart des réactions ont besoin d'un petit coup de pouce : l'énergie d'activation, comme l'allumette qui "
            "enflamme le gaz. Plus il fait chaud, plus les réactions vont vite : c'est pour ça qu'on garde les aliments au réfrigérateur.",
            "Un catalyseur accélère une réaction sans être consommé. Les pots catalytiques des voitures en utilisent, et nos cellules "
            "fonctionnent grâce à des milliers de catalyseurs naturels, les enzymes.",
        ],
        'expert': [
            "Stœchiométrie : les coefficients d'une équation équilibrée donnent les proportions en moles. Brûler 16 g de méthane (1 mol) "
            "consomme 64 g de dioxygène et produit 44 g de CO₂ et 36 g d'eau : 80 g de réactifs, 80 g de produits.",
            "Thermochimie : l'enthalpie de réaction ΔᵣH est négative pour une réaction exothermique (combustion du méthane : "
            "ΔᵣH° ≈ −890 kJ/mol, eau liquide). La spontanéité est donnée par l'enthalpie libre ΔG = ΔH − TΔS < 0 ; à l'équilibre, "
            "ΔᵣG° = −RT ln K.",
            "Cinétique : la constante de vitesse suit la loi d'Arrhenius, k = A · exp(−Eₐ / RT). Pour une énergie d'activation de l'ordre de "
            "50 kJ/mol, la vitesse double à peu près tous les 10 °C autour de la température ambiante. Un catalyseur abaisse Eₐ sans modifier "
            "ΔG ni la position de l'équilibre.",
        ],
        'formulas': [
            {'f': 'CH₄ + 2 O₂ → CO₂ + 2 H₂O', 'l': 'combustion du méthane'},
            {'f': 'ΔG = ΔH − T · ΔS', 'l': 'spontanéité d\'une réaction'},
            {'f': 'k = A · e^(−Eₐ / RT)', 'l': 'loi d\'Arrhenius'},
        ],
        'numbers': [
            {'v': '≈ −890 kJ/mol', 'l': 'chaleur dégagée par la combustion du méthane'},
            {'v': '× 2 tous les 10 °C', 'l': 'ordre de grandeur de l\'accélération d\'une réaction'},
            {'v': '80 g → 80 g', 'l': 'masse conservée : 16 g de méthane + 64 g de dioxygène'},
        ],
        'exp': {
            'title': 'Le volcan',
            'steps': [
                "Pose un verre dans une assiette et mets-y une cuillère à café de bicarbonate de soude.",
                "Verse doucement un peu de vinaigre.",
                "Ça mousse ! Le bicarbonate et l'acide du vinaigre réagissent en produisant un gaz, le dioxyde de carbone, qui forme les bulles.",
            ],
            'safety': 'Fais-le avec un adulte, et ne mélange jamais d\'autres produits ménagers entre eux.',
        },
        'svg': svg_reaction(),
        'caption': "Une molécule de méthane et deux de dioxygène deviennent une molécule de dioxyde de carbone et deux d'eau : les atomes sont les mêmes, seulement réarrangés.",
        'related': ['molecules', 'energie', 'acides-bases'],
    },
    {
        'id': 'acides-bases', 'domain': 'chimie', 'title': 'Acides, bases et pH',
        'tagline': 'Le citron, le savon et l\'échelle de 0 à 14',
        'kid': [
            "Le jus de citron et le vinaigre ont un goût acide : ce sont des acides. Le savon et le bicarbonate de soude sont au contraire "
            "des bases (on dit aussi qu'ils sont basiques). L'eau pure, elle, est neutre.",
            "Pour dire à quel point une solution est acide ou basique, on utilise une échelle de 0 à 14 : le pH. En dessous de 7, c'est "
            "acide ; 7, c'est neutre ; au-dessus de 7, c'est basique.",
            "Les acides forts et les bases fortes sont dangereux : ils brûlent la peau. On ne goûte jamais un produit inconnu et on ne mélange "
            "jamais des produits ménagers.",
        ],
        'dyk': "Ton estomac contient un acide très fort, avec un pH d'environ 1,5 à 3,5, pour digérer les aliments. Il est protégé par une "
               "couche de mucus qui l'empêche de se digérer lui-même.",
        'more': [
            "Un acide est une substance capable de céder un proton (un ion H⁺) ; une base, une substance capable de le capter. Quand on "
            "mélange un acide et une base, ils se neutralisent : c'est ce que font les médicaments contre les brûlures d'estomac.",
            "L'échelle de pH est logarithmique : quand le pH baisse d'une unité, la solution devient dix fois plus acide. Un jus de citron "
            "(pH ≈ 2) est donc environ 100 000 fois plus acide que l'eau pure (pH 7).",
            "Le pH compte partout : notre sang doit rester entre 7,35 et 7,45 ; et l'acidification des océans, causée par le CO₂ que nous "
            "rejetons, menace les coraux et les coquillages.",
        ],
        'expert': [
            "Définition : pH = −log₁₀ a(H₃O⁺) ≈ −log₁₀ [H₃O⁺] en solution diluée. L'eau s'autoprotolyse : 2 H₂O ⇌ H₃O⁺ + HO⁻, avec "
            "Kₑ = [H₃O⁺][HO⁻] = 10⁻¹⁴ à 25 °C, d'où un pH neutre de 7 à 25 °C, mais d'environ 6,1 à 100 °C.",
            "Force d'un acide : constante d'acidité Kₐ, pKₐ = −log Kₐ (acide acétique : pKₐ ≈ 4,76). Équation de Henderson-Hasselbalch : "
            "pH = pKₐ + log([A⁻]/[AH]). Les solutions tampons, mélanges d'un acide faible et de sa base conjuguée, stabilisent le pH : "
            "le couple CO₂/hydrogénocarbonate maintient celui du sang.",
            "Les indicateurs colorés changent de couleur selon le pH (phénolphtaléine : virage vers 8,2 à 10 ; hélianthine : 3,1 à 4,4). "
            "Pour une mesure précise, on utilise un pH-mètre, une électrode de verre dont la tension varie d'environ 59 mV par unité de pH "
            "à 25 °C (loi de Nernst).",
        ],
        'formulas': [
            {'f': 'pH = −log₁₀ [H₃O⁺]', 'l': 'définition (solution diluée)'},
            {'f': 'Kₑ = [H₃O⁺] · [HO⁻] = 10⁻¹⁴', 'l': 'produit ionique de l\'eau à 25 °C'},
            {'f': 'pH = pKₐ + log([A⁻] / [AH])', 'l': 'Henderson-Hasselbalch'},
        ],
        'numbers': [
            {'v': 'pH ≈ 2', 'l': 'jus de citron'},
            {'v': '7,35 – 7,45', 'l': 'pH du sang'},
            {'v': '≈ 8,1', 'l': 'pH de l\'eau de mer aujourd\'hui'},
        ],
        'exp': {
            'title': 'Le chou rouge qui change de couleur',
            'steps': [
                "Avec un adulte, fais chauffer quelques feuilles de chou rouge coupées dans de l'eau pendant dix minutes, puis filtre le jus violet.",
                "Verse un peu de ce jus dans un verre de vinaigre : il devient rouge-rose.",
                "Verse-en dans un verre d'eau avec une cuillère de bicarbonate : il vire au bleu-vert. Le chou contient des pigments qui "
                "changent de couleur selon le pH.",
            ],
            'safety': 'Utilise seulement vinaigre, citron et bicarbonate : jamais de produits ménagers.',
        },
        'svg': svg_ph(),
        'caption': "Chaque unité de pH correspond à un facteur dix : le vinaigre (pH ≈ 3) est environ 10 000 fois plus acide que l'eau pure (pH 7).",
        'related': ['reaction-chimique', 'molecules'],
    },
]


def validate():
    ids = [n['id'] for n in NOTIONS]
    assert len(ids) == len(set(ids)), 'identifiants en double'
    doms = {d['id'] for d in DOMAINS}
    for n in NOTIONS:
        assert n['domain'] in doms, n['id']
        for r in n['related']:
            assert r in ids, (n['id'], r)
        for k in ('kid', 'more', 'expert'):
            assert n[k] and all(isinstance(p, str) and p for p in n[k]), (n['id'], k)
        ET.fromstring(n['svg'])   # le schéma doit être du SVG valide
    for s in START:
        assert s in ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'site', 'data', 'bases.json'))
    a = ap.parse_args()
    validate()
    data = {'version': 1, 'title': 'Comprendre',
            'intro': "Les bases de la physique et de la chimie, expliquées pas à pas : chaque notion se lit à trois niveaux, "
                     "du plus simple (dès 10 ans) au niveau ingénieur.",
            'domains': DOMAINS, 'start': START,
            'notions': [{k: v for k, v in n.items() if v not in (None, '')} for n in NOTIONS]}
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print(f'{len(NOTIONS)} notions écrites dans {a.out} ({os.path.getsize(a.out) // 1024} Ko)')


if __name__ == '__main__':
    main()
