# Rendu Mairie — Projet Duo Papillon

Ce dossier contient les rendus destinés à la **présentation à la mairie** :
la maison est intégrée sur son terrain, **tout l'ATH (arbres de haute tige)
et tout le chantier sont retirés**, avec **3,50 m de bordure façade** sur
les quatre côtés.

## Fichiers

| Fichier | Description |
|---|---|
| `page-A3-mairie.pdf` | **Page A3 paysage imprimable** (420 × 297 mm, 300 dpi) contenant le plan de masse et la vue 3D conceptuelle, avec cartouche. |
| `page-A3-mairie.png` | Version PNG de la page A3 (4961 × 3508 px, 300 dpi). |
| `plan-de-masse.png` | Plan de masse seul : maison sur terrain engazonné, parcelle, allée d'accès, cotes, flèche nord, échelle graphique. |
| `vue-3d-conceptuelle.png` | Vue 3D conceptuelle réaliste de la maison finie (logements A bleu-gris / B ocre, toiture papillon, vitrages, terrasse bois, terrain). |
| `generate_renders.py` | Script Python générant tous les rendus à partir des données géométriques du fichier `Duo Papillon.html`. |

## Implantation

- **Emprise maison** : 11,83 m × 10,71 m (toiture : 13,03 m × 11,91 m avec débords)
- **Retrait façade** : 3,50 m sur les 4 côtés (zone constructible)
- **Parcelle affichée** : environ 21 m × 19 m
- **Allée d'accès** : 3,00 m de large côté sud
- **Terrasse** : bois, côté nord (deck 6,71 m × 1,39 m)

## Caractéristiques du projet

- **2 logements jumelés** (A · J1 et B · J2), SHAB 48,8 m² chacun
- Murs en **béton imprimé 3D** (deux peaux + isolation)
- **Toiture papillon** (pente vers le refend central)
- **Poteaux BA** et chaînage en béton armé
- **Menuiseries aluminium** double vitrage
- **Portes d'entrée bois** côté porche
- **Terrasse bois** côté nord

## Régénération

```bash
python3 rendu-mairie/generate_renders.py
```

Dépendances : `pillow`, `numpy`.

## Données source

Les géométries (murs, toiture, menuiseries, dalle, terrasse) sont extraites
automatiquement du fichier `Duo Papillon.html` (objet `DATA` embarqué),
garantissant la cohérence avec la maquette 3D interactive.
