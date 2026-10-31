# Acceptation des conditions dans l'application

*Projet — à faire relire. Non actif : à brancher au premier lancement lorsque la vente sera lancée.*

## 1. Texte à afficher (écran de premier lancement)

> **Bienvenue dans [NOM]**
>
> Avant de commencer, merci de lire et d'accepter :
> - ☐ J'ai lu et j'accepte les **Conditions d'utilisation et la licence** (lien).
> - ☐ J'ai lu la **Politique de confidentialité** (lien). Mes données restent sur mon téléphone.
> - ☐ *(acheteur uniquement)* Je demande la **fourniture immédiate** de l'application et je reconnais perdre ainsi mon **droit de rétractation** (art. L221-28 13° du Code de la consommation).
>
> [ Refuser et quitter ]   [ **J'accepte et je continue** ]

Règles d'affichage : les cases ne sont **pas pré-cochées** ; le bouton « J'accepte » n'est actif qu'une fois les cases obligatoires cochées ; les documents complets sont consultables **avant** d'accepter, depuis cet écran, et à tout moment depuis l'écran d'aide ; une nouvelle version des CGU redemande l'acceptation.

## 2. Preuve de l'acceptation (à enregistrer)

Pour pouvoir prouver l'acceptation (art. 1366 et 1367 du Code civil sur l'écrit et la signature électroniques ; art. L221-13 sur la confirmation sur support durable), l'application enregistre, au moment de l'appui sur « J'accepte » :

- date et heure (UTC) ;
- version de l'application et **numéro de version des CGU** acceptées ;
- identifiant de l'appareil (code à 6 lettres) et, le cas échéant, le code d'activation ;
- l'empreinte (SHA-256) du texte exact des CGU affichées ;
- la liste des cases cochées.

Conservation : sur l'appareil (fichier `acceptation.json` dans les données privées de l'application) **et**, lorsque le vendeur disposera d'un point de collecte (formulaire ou serveur), copie envoyée au vendeur avec accusé de réception e-mail au client (support durable). À défaut de serveur, le client reçoit par e-mail, avec son code d'activation, une copie des CGV/CGU acceptées.

## 3. Emplacement dans le code (à faire lors de l'activation)

- Afficher cet écran avant `LockActivity` / l'écran d'activation.
- Ajouter dans l'écran d'aide : « Conditions d'utilisation », « Confidentialité », « Mentions légales » (ouverture des fichiers `legal/*.md` embarqués dans les assets).
- Ne jamais bloquer l'accès aux documents derrière l'acceptation.
