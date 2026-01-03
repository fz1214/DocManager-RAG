# DocManager - Application de Gestion de Documents avec IA

## 🎯 Description

**DocManager** est une application web moderne et intuitive qui permet aux utilisateurs de gérer leurs documents PDF et d'interagir avec eux grâce à l'intelligence artificielle. L'application combine stockage cloud, indexation automatique et capacités d'IA pour transformer la façon dont on interagit avec les documents.

## ✨ Fonctionnalités principales

### 🔐 Authentification
- **Inscription/Connexion** sécurisée avec gestion des sessions
- **Interface moderne** avec validation en temps réel
- **Indicateur de force du mot de passe** avec feedback visuel

### 📄 Gestion de Documents
- **Upload de fichiers PDF** avec drag & drop
- **Indexation automatique** des documents
- **Stockage cloud** sur Azure Blob Storage
- **Organisation intelligente** des documents par utilisateur

### 🤖 Assistant IA (RAG)
- **Questions-réponses intelligentes** sur vos documents
- **Historique des interactions** avec l'IA
- **Interface intuitive** pour poser des questions
- **Réponses contextuelles** basées sur le contenu des documents

### 📊 Tableau de Bord
- **Vue d'ensemble** de votre activité
- **Statistiques en temps réel** (documents, questions, espace)
- **Documents et questions récents** avec accès rapide

## 🎨 Design et Interface

### ✨ Caractéristiques du Design
- **Interface moderne et épurée** inspirée des meilleures pratiques UX
- **Palette de couleurs cohérente** avec variables CSS personnalisables
- **Animations fluides** et transitions élégantes
- **Design responsive** adapté à tous les écrans
- **Icônes FontAwesome** pour une meilleure lisibilité

### 🎯 Améliorations Apportées
- **Header repensé** : DocManager déplacé en haut à droite avec nouveau logo
- **Navigation intuitive** : Icônes et libellés clairs
- **Formulaires améliorés** : Champs avec icônes et validation visuelle
- **Cartes interactives** : Hover effects et animations
- **Messages flash** : Notifications élégantes et positionnées

## 🏗️ Architecture Technique

### Backend
- **Flask 3.0.3** - Framework web Python moderne
- **Azure Services** - Stockage et base de données cloud
- **LangChain** - Framework d'IA pour le traitement du langage
- **Azure OpenAI** - Modèles d'IA avancés

### Frontend
- **HTML5 sémantique** avec templates Jinja2
- **CSS3 moderne** avec variables CSS et Flexbox/Grid
- **JavaScript vanilla** pour les interactions utilisateur
- **FontAwesome 6** pour les icônes

### Base de Données
- **Azure Table Storage** pour les métadonnées
- **Azure Blob Storage** pour les fichiers PDF
- **Azure Cognitive Search** pour l'indexation vectorielle

## 🚀 Installation et Configuration

### Prérequis
- Python 3.8+
- Compte Azure avec services configurés
- Variables d'environnement Azure configurées

### Installation
```bash
# Cloner le projet
git clone <repository-url>
cd app_doc

# Créer l'environnement virtuel
python -m venv .venv

# Activer l'environnement (Windows)
.venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python main.py
```

### Configuration
1. Configurer les variables d'environnement Azure
2. Mettre à jour les clés d'accès dans `backend_services.py`
3. Configurer les conteneurs Azure Storage

## 📱 Interface Utilisateur

### 🎨 Pages Principales

#### Page de Connexion
- **Design moderne** avec gradient bleu
- **Champs de saisie** avec icônes et validation
- **Bouton de connexion** avec animation hover
- **Lien d'inscription** intégré

#### Page d'Inscription
- **Formulaire complet** avec validation
- **Indicateur de force** du mot de passe en temps réel
- **Bouton d'affichage** du mot de passe
- **Validation des champs** avec feedback

#### Tableau de Bord
- **Statistiques visuelles** avec icônes colorées
- **Grille responsive** pour les sections récentes
- **États vides** avec appels à l'action
- **Navigation rapide** vers les fonctionnalités

#### Gestion des Documents
- **Upload simplifié** avec bouton moderne
- **Grille de documents** avec cartes interactives
- **Actions rapides** (suppression, visualisation)
- **Statuts visuels** avec badges colorés

#### Assistant IA
- **Interface de questions** intuitive
- **Sélection de documents** avec dropdown
- **Zone de texte** auto-redimensionnable
- **Historique organisé** par document

### 🎯 Améliorations UX
- **Feedback visuel** sur toutes les actions
- **Transitions fluides** entre les états
- **Responsive design** pour mobile et desktop
- **Accessibilité** améliorée avec labels et contrastes

## 🔧 Fonctionnalités Techniques

### Sécurité
- **Hachage des mots de passe** avec SHA-256
- **Gestion des sessions** sécurisée
- **Validation des entrées** côté serveur
- **Authentification requise** pour toutes les pages

### Performance
- **Lazy loading** des composants
- **Optimisation des requêtes** Azure
- **Cache des sessions** avec expiration
- **Compression des assets** statiques

### Scalabilité
- **Architecture modulaire** avec blueprints Flask
- **Services backend** séparés et réutilisables
- **Configuration centralisée** des variables
- **Gestion d'erreurs** robuste

## 🌟 Points Forts

### Design
- ✅ **Interface moderne** et professionnelle
- ✅ **Cohérence visuelle** sur toutes les pages
- ✅ **Responsive design** pour tous les appareils
- ✅ **Animations fluides** et transitions élégantes

### Fonctionnalités
- ✅ **Gestion complète** des documents PDF
- ✅ **Assistant IA intelligent** avec RAG
- ✅ **Authentification sécurisée** et intuitive
- ✅ **Tableau de bord** informatif et interactif

### Technique
- ✅ **Architecture robuste** et maintenable
- ✅ **Intégration Azure** complète
- ✅ **Code propre** et bien documenté
- ✅ **Gestion d'erreurs** professionnelle

## 🚀 Roadmap Future

### Améliorations Planifiées
- [ ] **Mode sombre** pour l'interface
- [ ] **Notifications push** en temps réel
- [ ] **Collaboration** multi-utilisateurs
- [ ] **API REST** pour intégrations tierces
- [ ] **Analytics avancés** d'utilisation

### Optimisations
- [ ] **Cache Redis** pour les performances
- [ ] **CDN** pour les assets statiques
- [ ] **Tests automatisés** complets
- [ ] **CI/CD** avec GitHub Actions

## 📄 Licence

© 2025 DocManager. Tous droits réservés.

---

**DocManager** - Transformez vos documents en connaissances avec l'IA ! 🚀
