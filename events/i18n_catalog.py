"""Traductions de l'interface invités (texte source en français).

Les textes personnalisés par l'organisateur (titres, catégories, lieux…) ne sont PAS ici :
ils sont saisis dans chaque langue via l'assistant.
Pour compléter le lingala : ajouter les paires dans CATALOG["ln"], puis
`python manage.py build_translations --missing` pour voir ce qui manque.
"""

EN = {
    "✧ AVEC TOUT NOTRE AMOUR ✧": "✧ WITH ALL OUR LOVE ✧", "Avec joie, nous célébrons votre présence à nos côtés ! 🥂": "We are overjoyed to celebrate with you by our side! 🥂",
    "C'est aujourd'hui !": "It's today!", "Le grand jour approche !": "The big day is coming!", "lieux de fête": "party venues", "Lieu unique · Magie garantie ✨": "One venue · Magic guaranteed ✨",
    "CARTE D'INVITATION AU MARIAGE": "WEDDING INVITATION", "CARTE D'INVITATION": "INVITATION", "Un grand merci pour votre réponse positive": "Thank you so much for saying yes",
    "Événement en %(n)s lieux différents": "Event in %(n)s different venues", "Lieu unique · Célébration": "One venue · Celebration",
    "Nous avons hâte de célébrer ce jour spécial avec vous, %(name)s ! ✨": "We can't wait to celebrate this special day with you, %(name)s! ✨",
    "Ouvrir le mur des vœux": "Open the wish wall", "Scannez ou touchez le QR code : mur des vœux et vos photos": "Scan or tap the QR code: wish wall and your photos",
    "Les mariés": "The couple", "Galerie": "Gallery", "Nos photos": "Our photos", "Merci d’être à nos côtés": "Thank you for being with us", "Retour en haut": "Back to top", "Défiler": "Scroll down", "Nous nous marions": "We're getting married",

    "Langue": "Language", "Annuler": "Undo", "Préparez-vous…": "Get ready…", "Bonjour": "Hello",
    "Dites-nous d’abord qui vous êtes 😊": "Tell us who you are first 😊", "Vœu supprimé": "Wish deleted", "Envoyé ✦": "Sent ✦",
    "Merci": "Thank you", "Votre carte personnalisée est prête 🎉": "Your personal card is ready 🎉",
    "Votre réponse a bien été enregistrée. Vous nous manquerez !": "Your reply has been saved. We will miss you!",
    "Télécharger ma carte": "Download my card", "Mur des vœux": "Wish wall", "Y aller": "Get there", "Liste de cadeaux": "Gift list",
    "Je l’offre": "I'll give it", "Déjà offert": "Already given", "Votre prénom et nom": "Your first and last name", "Quantité": "Quantity",
    "Livraison": "Delivery", "Merci ! Le cadeau est réservé 💛": "Thank you! The gift is reserved 💛", "Confirmer": "Confirm", "restant(s)": "left",
    "Carte": "Map", "Distance": "Distance", "Direction": "Direction", "Arrivée estimée": "Estimated arrival", "Mode économie": "Battery saver",
    "Votre position reste sur votre téléphone : elle n’est jamais envoyée.": "Your location stays on your phone: it is never sent.",
    "La distance est calculée en ligne droite.": "Distance is measured in a straight line.",
    "Parcours de la journée": "Today's route", "Me guider avec mon appli": "Guide me with my app",
    "nord": "north", "nord-est": "north-east", "est": "east", "sud-est": "south-east", "sud": "south", "sud-ouest": "south-west", "ouest": "west", "nord-ouest": "north-west",
    "%(place)s commence dans %(min)s min, il vous reste environ %(eta)s min de trajet.": "%(place)s starts in %(min)s min, and you have about %(eta)s min to go.",
    "Bienvenue": "Welcome", "Vous êtes arrivé·e à": "You have arrived at", "✅ Je suis arrivé·e": "✅ I'm here", "💬 Laisser un vœu": "💬 Leave a wish",
    "Fermer": "Close", "Votre place vous attend 💛": "Your seat is waiting for you 💛", "Merci ! Les hôtes savent que vous êtes là.": "Thank you! The hosts know you're here.",
    "Activez la localisation pour vous voir sur la carte.": "Turn on location to see yourself on the map.",
    "Position mise à jour moins souvent pour économiser la batterie": "Location updated less often to save battery",
    "Cher·e": "Dear", "Scannez pour le mur des vœux et vos photos": "Scan for the wish wall and your photos",
    "Plus que…": "Only…", "Jours": "Days", "Heures": "Hours", "Min": "Min", "Sec": "Sec",
    "Notre histoire": "Our story", "Notre histoire d’amour": "Our love story", "Programme": "Programme", "Le programme de la journée": "The day's programme",
    "Musique": "Music", "La chanson de la fête": "The song of the day", "Streamer sur": "Stream on", "Serez-vous des nôtres ?": "Will you join us?",
    "Répondre à l’invitation": "Reply to the invitation", "Prénom": "First name", "Nom": "Last name", "E-mail (facultatif)": "Email (optional)",
    "Téléphone (facultatif)": "Phone (optional)", "Serez-vous présent·e ?": "Will you attend?", "Oui, avec joie": "Yes, with joy",
    "Désolé·e, je ne pourrai pas": "Sorry, I can't make it", "Vous êtes…": "You are…", "Accompagnant·e·s": "Plus-ones", "Vos enfants": "Your children",
    "+ Ajouter un enfant": "+ Add a child", "Un mot pour les hôtes (facultatif)": "A note for the hosts (optional)", "Vos vœux (facultatif)": "Your wishes (optional)",
    "Envoyer ma réponse": "Send my reply", "Prénom de l’accompagnant·e": "Plus-one's first name", "Âge": "Age",
    "reste avec ses parents": "stays with the parents", "(sans chaise)": "(no chair)", "table des enfants": "kids' table", "place adulte": "adult seat",
    "Encore un petit détail…": "One more little thing…",
    "Nous voulons que chacun se sente à l’aise à table et puisse discuter avec ses voisins 💬": "We want everyone to feel at ease at the table and chat with their neighbours 💬",
    "Dans quelles langues aimez-vous converser ?": "Which languages do you enjoy talking in?",
    "Vous pouvez en choisir plusieurs, ou passer cette étape.": "You can pick several, or skip this step.",
    "Autre": "Other", "💖 Continuer": "💖 Continue", "Passer": "Skip", "Le prénom est obligatoire": "First name is required",
    "Plein écran": "Full screen", "vœux": "wishes", "réactions": "reactions", "Bientôt": "Coming up", "Scannez pour laisser votre vœu 💛": "Scan to leave your wish 💛",
    "Histoire": "Story", "Messages d’amour de nos invités": "Love notes from our guests", "Écouter": "Listen", "Moments forts": "Highlights",
    "Laissez un vœu": "Leave a wish", "Votre message…": "Your message…", "Envoyer mon vœu": "Send my wish",
    "Vous n’avez pas votre carte ? Dites-nous qui vous êtes, une seule fois.": "Don't have your card? Tell us who you are, just once.",
    "Reconnu·e grâce au QR code de votre carte.": "Recognised thanks to the QR code on your card.", "Supprimer mon vœu": "Delete my wish",
    "Envoyer une photo ou une vidéo": "Send a photo or video", "Photo envoyée aux mariés 📸": "Photo sent to the couple 📸", "Légende (facultatif)": "Caption (optional)",
}

IT = {
    "✧ AVEC TOUT NOTRE AMOUR ✧": "✧ CON TUTTO IL NOSTRO AMORE ✧", "Avec joie, nous célébrons votre présence à nos côtés ! 🥂": "Con gioia festeggiamo la vostra presenza al nostro fianco! 🥂",
    "C'est aujourd'hui !": "È oggi!", "Le grand jour approche !": "Il grande giorno si avvicina!", "lieux de fête": "luoghi di festa", "Lieu unique · Magie garantie ✨": "Un solo luogo · Magia garantita ✨",
    "CARTE D'INVITATION AU MARIAGE": "PARTECIPAZIONE DI NOZZE", "CARTE D'INVITATION": "INVITO", "Un grand merci pour votre réponse positive": "Grazie di cuore per aver accettato",
    "Événement en %(n)s lieux différents": "Evento in %(n)s luoghi diversi", "Lieu unique · Célébration": "Un solo luogo · Celebrazione",
    "Nous avons hâte de célébrer ce jour spécial avec vous, %(name)s ! ✨": "Non vediamo l'ora di festeggiare questo giorno speciale con te, %(name)s! ✨",
    "Ouvrir le mur des vœux": "Apri il muro degli auguri", "Scannez ou touchez le QR code : mur des vœux et vos photos": "Scansiona o tocca il QR code: muro degli auguri e le tue foto",
    "Les mariés": "Gli sposi", "Galerie": "Galleria", "Nos photos": "Le nostre foto", "Merci d’être à nos côtés": "Grazie di essere con noi", "Retour en haut": "Torna su", "Défiler": "Scorri", "Nous nous marions": "Ci sposiamo",

    "Langue": "Lingua", "Annuler": "Annulla", "Préparez-vous…": "Preparatevi…", "Bonjour": "Ciao",
    "Dites-nous d’abord qui vous êtes 😊": "Dicci prima chi sei 😊", "Vœu supprimé": "Desiderio eliminato", "Envoyé ✦": "Inviato ✦",
    "Merci": "Grazie", "Votre carte personnalisée est prête 🎉": "Il tuo invito personalizzato è pronto 🎉",
    "Votre réponse a bien été enregistrée. Vous nous manquerez !": "La tua risposta è stata registrata. Ci mancherai!",
    "Télécharger ma carte": "Scarica il mio invito", "Mur des vœux": "Muro dei desideri", "Y aller": "Come arrivare", "Liste de cadeaux": "Lista regali",
    "Je l’offre": "Lo regalo io", "Déjà offert": "Già regalato", "Votre prénom et nom": "Nome e cognome", "Quantité": "Quantità",
    "Livraison": "Consegna", "Merci ! Le cadeau est réservé 💛": "Grazie! Il regalo è prenotato 💛", "Confirmer": "Conferma", "restant(s)": "rimasti",
    "Carte": "Mappa", "Distance": "Distanza", "Direction": "Direzione", "Arrivée estimée": "Arrivo stimato", "Mode économie": "Risparmio batteria",
    "Votre position reste sur votre téléphone : elle n’est jamais envoyée.": "La tua posizione resta sul telefono: non viene mai inviata.",
    "La distance est calculée en ligne droite.": "La distanza è calcolata in linea d'aria.",
    "Parcours de la journée": "Percorso della giornata", "Me guider avec mon appli": "Guidami con la mia app",
    "nord": "nord", "nord-est": "nord-est", "est": "est", "sud-est": "sud-est", "sud": "sud", "sud-ouest": "sud-ovest", "ouest": "ovest", "nord-ouest": "nord-ovest",
    "%(place)s commence dans %(min)s min, il vous reste environ %(eta)s min de trajet.": "%(place)s inizia tra %(min)s min, ti restano circa %(eta)s min di strada.",
    "Bienvenue": "Benvenuto/a", "Vous êtes arrivé·e à": "Sei arrivato/a a", "✅ Je suis arrivé·e": "✅ Sono arrivato/a", "💬 Laisser un vœu": "💬 Lascia un desiderio",
    "Fermer": "Chiudi", "Votre place vous attend 💛": "Il tuo posto ti aspetta 💛", "Merci ! Les hôtes savent que vous êtes là.": "Grazie! Gli ospiti sanno che sei qui.",
    "Activez la localisation pour vous voir sur la carte.": "Attiva la localizzazione per vederti sulla mappa.",
    "Position mise à jour moins souvent pour économiser la batterie": "Posizione aggiornata meno spesso per risparmiare batteria",
    "Cher·e": "Caro/a", "Scannez pour le mur des vœux et vos photos": "Scansiona per il muro dei desideri e le foto",
    "Plus que…": "Mancano…", "Jours": "Giorni", "Heures": "Ore", "Min": "Min", "Sec": "Sec",
    "Notre histoire": "La nostra storia", "Notre histoire d’amour": "La nostra storia d'amore", "Programme": "Programma", "Le programme de la journée": "Il programma della giornata",
    "Musique": "Musica", "La chanson de la fête": "La canzone della festa", "Streamer sur": "Ascolta su", "Serez-vous des nôtres ?": "Sarai dei nostri?",
    "Répondre à l’invitation": "Rispondi all'invito", "Prénom": "Nome", "Nom": "Cognome", "E-mail (facultatif)": "E-mail (facoltativa)",
    "Téléphone (facultatif)": "Telefono (facoltativo)", "Serez-vous présent·e ?": "Sarai presente?", "Oui, avec joie": "Sì, con gioia",
    "Désolé·e, je ne pourrai pas": "Purtroppo non potrò", "Vous êtes…": "Sei…", "Accompagnant·e·s": "Accompagnatori", "Vos enfants": "I tuoi figli",
    "+ Ajouter un enfant": "+ Aggiungi un bambino", "Un mot pour les hôtes (facultatif)": "Un pensiero per gli sposi (facoltativo)", "Vos vœux (facultatif)": "I tuoi auguri (facoltativi)",
    "Envoyer ma réponse": "Invia la risposta", "Prénom de l’accompagnant·e": "Nome dell'accompagnatore", "Âge": "Età",
    "reste avec ses parents": "resta con i genitori", "(sans chaise)": "(senza sedia)", "table des enfants": "tavolo dei bambini", "place adulte": "posto adulto",
    "Encore un petit détail…": "Ancora un piccolo dettaglio…",
    "Nous voulons que chacun se sente à l’aise à table et puisse discuter avec ses voisins 💬": "Vogliamo che tutti si sentano a proprio agio a tavola e possano chiacchierare con i vicini 💬",
    "Dans quelles langues aimez-vous converser ?": "In quali lingue ti piace conversare?",
    "Vous pouvez en choisir plusieurs, ou passer cette étape.": "Puoi sceglierne più di una, oppure saltare.",
    "Autre": "Altra", "💖 Continuer": "💖 Continua", "Passer": "Salta", "Le prénom est obligatoire": "Il nome è obbligatorio",
    "Plein écran": "Schermo intero", "vœux": "desideri", "réactions": "reazioni", "Bientôt": "A breve", "Scannez pour laisser votre vœu 💛": "Scansiona per lasciare il tuo desiderio 💛",
    "Histoire": "Storia", "Messages d’amour de nos invités": "Messaggi d'amore dai nostri ospiti", "Écouter": "Ascolta", "Moments forts": "Momenti speciali",
    "Laissez un vœu": "Lascia un desiderio", "Votre message…": "Il tuo messaggio…", "Envoyer mon vœu": "Invia il mio desiderio",
    "Vous n’avez pas votre carte ? Dites-nous qui vous êtes, une seule fois.": "Non hai il tuo invito? Dicci chi sei, una volta sola.",
    "Reconnu·e grâce au QR code de votre carte.": "Riconosciuto/a grazie al QR code del tuo invito.", "Supprimer mon vœu": "Elimina il mio desiderio",
    "Envoyer une photo ou une vidéo": "Invia una foto o un video", "Photo envoyée aux mariés 📸": "Foto inviata agli sposi 📸", "Légende (facultatif)": "Didascalia (facoltativa)",
}

# Lingala : seulement des traductions déjà fournies dans les modèles existants de Miel.
# À compléter par une personne qui parle lingala.
LN = {
    "Mur des vœux": "Lisango ya Mabondeli", "Laissez un vœu": "Tika lobondeli", "Votre prénom et nom": "Nkombo na yo",
    "Votre message…": "Maloba na yo ya bolingo...", "Envoyer mon vœu": "Tinda lobondeli na ngai", "Nom": "Nkombo",
}

CATALOG = {"en": EN, "it": IT, "ln": LN}
