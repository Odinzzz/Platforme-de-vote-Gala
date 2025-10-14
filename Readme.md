Parfait, on repart à zéro proprement 💣🔁
Voici la **procédure complète** pour :

1. Arrêter et supprimer le conteneur Docker
2. Supprimer l’image Docker
3. Supprimer tous les fichiers du dossier `GalaApp`
4. Re-cloner ton dépôt Git
5. Rebuilder l’image
6. Relancer le conteneur avec les bons volumes et ports

---

## 🧼 1. Stopper et supprimer le conteneur

```bash
docker stop gala
docker rm gala
```

---

## 🗑️ 2. Supprimer l’image Docker

```bash
docker rmi plateforme-gala
```

> Si ça bloque, ajoute `--force`

---

## 🧹 3. Vider le dossier GalaApp

Tu es dans `~/GalaApp`, donc :

```bash
cd ~
rm -rf GalaApp
mkdir GalaApp
cd GalaApp
```

---

## 🔁 4. Re-cloner ton dépôt Git

```bash
git clone https://github.com/TON-UTILISATEUR/TON-DEPOT.git .
```

---

## 🧱 5. Rebuild l’image Docker

```bash
docker build -t plateforme-gala .
```

---

## 🚀 6. Relancer le conteneur

Assure-toi que le dossier de données existe (ou recrée-le) :

```bash
mkdir -p /home/tommy/GalaData
```

Puis lance :

```bash
docker run -d --name gala \
  -p 5000:5000 \
  -e SECRET_KEY="change-me" \
  -v ~/home/tommy/GalaData:/app/data \
  plateforme-gala
```

---

## ✅ 7. Vérifier que tout roule

```bash
docker ps
docker logs -f gala
```

Puis dans ton navigateur :

```
http://TON-IP-PUBLIQUE:5000
```

---


