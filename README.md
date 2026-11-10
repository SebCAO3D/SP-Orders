# SP-Orders – Commandes Michelin Service Point

Application web mobile pour les garages Service Point : ils saisissent leurs besoins de réassort de pneus,
l'administrateur reçoit un **email récapitulatif** après l'heure limite et passe les commandes **à la main sur BibServ**.
Aucune commande n'est passée automatiquement.

**Page des garages** : https://sebcao3d.github.io/SP-Orders/?k=CLE_DU_GARAGE
(chaque garage a sa propre clé, indiquée dans l'onglet *Garages* du Google Sheet)

## Comment ça marche

| Élément | Rôle |
|---|---|
| **GitHub Pages** (ce dépôt) | Affiche la page des garages (`index.html`) |
| **Google Sheet** | Base de données : Commandes, Garages, Clients, Catalogue, Reglages |
| **Google Apps Script** | « Serveur » : vérifications, email récapitulatif, déclencheurs |

Après l'heure limite (réglable dans l'onglet *Reglages*, case B6), un email regroupe les lignes « En attente ».
Les garages commandent **uniquement via un client** (onglet *Clients*) : la carte du garage lui-même ne permet pas de choisir un pneu.
Une fois commandé sur BibServ, l'administrateur choisit **OK CDE** dans la colonne *Statut* de l'onglet *Commandes* :
le garage voit alors « Commandée » dans son suivi.

## Contenu du dépôt

| Fichier / dossier | À quoi il sert |
|---|---|
| `index.html` | La page des garages. **Doit rester à la racine** (c'est ce que GitHub Pages publie). |
| `logos/` | Logo de l'en-tête (`michelin-transparent.png`) et logos des garages et des clients (Euromaster, Keolis, Transdev, bestdrive, firststop, lenormant, points…), appelés depuis les colonnes `logo` du Sheet sous la forme `logos/nom.png`. |
| `sauvegarde/` | Copies de travail, sans effet sur le site : script Apps Script, récapitulatif complet, catalogue. |

## Mettre à jour l'application

- **La page** : remplacer `index.html` ici (crayon ou *Add file → Upload files*), puis recharger avec Ctrl+Maj+R.
- **Le script** : coller `sauvegarde/Code-Google-Apps-Script.txt` dans Apps Script, lancer *Commandes SP → 1. Installer*,
  puis *Déployer → Gérer les déploiements → crayon → Nouvelle version*. L'adresse du script ne change pas.
- Les deux fichiers fonctionnent ensemble : les mettre à jour tous les deux.

## Reproduire l'application

Toute la marche à suivre (structure des onglets, règles, installation de zéro, dépannage) est dans
`sauvegarde/RECAP-Application-Commandes-SP.md`.

## Sécurité

- Ce dépôt est **public** : n'y déposez jamais de clés de garages, de données clients ni de copie du Google Sheet.
- La clé d'un garage est son seul accès : la modifier dans l'onglet *Garages* invalide l'ancien lien.
