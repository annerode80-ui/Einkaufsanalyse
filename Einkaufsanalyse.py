"""
ARTIKEL-DATENMODELL:

produkt:
    Produktname aus dem Kassenbon (aktueller Arbeitswert)
produkt_original:
    Originalbezeichnung aus dem Kassenbon (unverändert)
produkt_standard:
    Vereinheitlichter Name für Auswertungen
    → ermöglicht Vergleichbarkeit zwischen Händlern
    → verbessert Lesbarkeit
bio:
    "ja" / "nein" / "unbekannt"
    → für Auswertungen
kategorie:
    Produktkategorie aus vorgegebener, erweiterbarer Liste
    → automatische Zuordnung möglich
menge:
    gekaufte Menge laut Kassenbon
einheit:
    Verpackungseinheit (z. B. "Glas", "Packung")
    → aus vorgegebener, erweiterbarer Liste
inhalt_menge:
    Inhalt der Verpackung (z. B. 200)
inhalt_einheit:
    Einheit des Inhalts (z. B. "g", "Stück")
einzelpreis:
    Kaufpreis für die gekaufte Einheit laut Kassenbon
haendler:
    Händler aus vorgegebener, erweiterbarer Liste
datum:
    Kaufdatum im ISO-Format (YYYY-MM-DD)
kalenderwoche:
    aus Datum abgeleitet, für Auswertungen
monat:
    aus Datum abgeleitet, für Auswertungen
bon_id:
    eindeutige ID aus Händler, Datum/Uhrzeit und Bonnummer
vollstaendig:
    True / False
    → Kennzeichnet, ob alle relevanten Felder gepflegt sind
"""

import json
from datetime import datetime
import re
from pypdf import PdfReader

"""
Lädt alle Einkäufe aus einer JSON-Datei.
Rückgabe: Liste von Artikel-Dictionaries
"""
def daten_laden(dateiname):
    try:
        with open(dateiname, "r", encoding="utf-8") as datei:
            einkaeufe = json.load(datei)
    except FileNotFoundError:
        print("Noch keine Datei vorhanden.")
        return []
    except json.JSONDecodeError:
        print("Datei ist fehlerhaft.")
        return []
    for artikel in einkaeufe:
        if not isinstance(artikel, dict):
            continue
        if 'produkt' not in artikel or str(artikel['produkt']).strip() == '':
            artikel['produkt'] = 'unbekannt'

        if 'kategorie' not in artikel or str(artikel['kategorie']).strip() == '':
            artikel['kategorie'] = 'unbekannt'

        if 'einheit' not in artikel or str(artikel['einheit']).strip() == '':
            artikel['einheit'] = 'unbekannt'

        if 'bio' not in artikel or artikel['bio'] not in ['ja', 'nein']:
            artikel['bio'] = 'unbekannt'

        if 'menge' not in artikel or artikel['menge'] is None or artikel['menge'] == '':
            artikel['menge'] = None

        if 'einzelpreis' not in artikel or artikel['einzelpreis'] is None or artikel['einzelpreis'] == '':
            artikel['einzelpreis'] = None

        if 'haendler' not in artikel or str(artikel['haendler']).strip() == '':
            artikel['haendler'] = 'unbekannt'

        if 'datum' not in artikel or artikel['datum'] is None or artikel['datum'] == '':
            artikel['datum'] = None
        else:
            datum_string = artikel['datum']
            try:
                datum_objekt = datetime.strptime(datum_string, "%Y-%m-%d")
            except ValueError:
                try:
                    datum_objekt = datetime.strptime(datum_string, "%d.%m.%Y")
                except ValueError:
                    datum_objekt = None
            if datum_objekt:
                artikel['datum'] = datum_objekt.strftime("%Y-%m-%d")
                artikel['kalenderwoche'] = datum_objekt.isocalendar().week
                artikel['monat'] = datum_objekt.month
        
        vollstaendigkeit_pruefen(artikel)
    return einkaeufe

"""
Speichert alle Einkäufe als JSON-Datei.
Parameter: einkaeufe: Liste von Artikel-Dictionaries
"""
def daten_speichern(dateiname, einkaeufe):
    with open(dateiname, "w", encoding="utf-8") as datei:
        json.dump(einkaeufe, datei, ensure_ascii=False, indent=4)

"""Lädt Stammdaten (Kategorien, Händler, Einheiten, Zuordnungen) aus JSON-Datei."""
def stammdaten_laden(dateiname):
    try:
        with open(dateiname, "r", encoding="utf-8") as datei:
            stammdaten = json.load(datei)
            return stammdaten
    except FileNotFoundError:
        print("Stammdaten-Datei nicht gefunden.")
        return {}
    except json.JSONDecodeError:
        print("Stammdaten-Datei ist fehlerhaft.")
        return {}

"""
Aktualisiert Stammdaten und speichert sie.
Wird verwendet, wenn neue Kategorien oder Zuordnungen gelernt wurden.
"""
def stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, dateiname):
    stammdaten["KATEGORIE_ZUORDNUNG"] = kategorie_zuordnung
    stammdaten_speichern(stammdaten_datei, stammdaten)

"""Speichert Stammdaten in eine JSON-Datei."""
def stammdaten_speichern(dateiname, stammdaten):
    with open(dateiname, "w", encoding="utf-8") as datei:
        json.dump(stammdaten, datei, ensure_ascii=False, indent=4)

"""Lädt das Mapping zwischen produkt_original und produkt_standard."""
def produkt_mapping_laden(dateiname):
    try:
        with open(dateiname, "r", encoding="utf-8") as datei:
            mapping = json.load(datei)
            return mapping
    except FileNotFoundError:
        print("Produkt-Mapping-Datei nicht gefunden.")
        return {}
    except json.JSONDecodeError:
        print("Produkt-Mapping-Datei ist fehlerhaft.")
        return {}

"""
Bestimmt den standardisierten Produktnamen.
Gibt den Mapping-Wert zurück, falls vorhanden, sonst den Originalnamen.
"""
def produkt_standard_bestimmen(produkt, mapping):
    if produkt in mapping:
        return mapping[produkt]
    return produkt

"""
Ergänzt das Mapping für neue Artikel.
Für unbekannte Produkte kann ein Standardname eingegeben werden. Mapping wird direkt erweitert.
"""
def produkt_mapping_ergaenzen(artikel_liste, mapping):
    bearbeitet = set()
    for artikel in artikel_liste:
        if artikel['produkt_standard'] == artikel['produkt_original'] and artikel['produkt_original'] not in bearbeitet:
            
            wert = input(
                f'Standardname für "{artikel["produkt_original"]}" eingeben (Enter = Artikel überspringen): '
            ).strip()

            if wert != '':
                wert = wert.title()

                artikel['produkt_standard'] = wert
                mapping[artikel['produkt_original']] = wert
            
            bearbeitet.add(artikel['produkt_original'])

    return artikel_liste, mapping

"""Speichert das Produkt-Mapping in eine JSON-Datei."""
def produkt_mapping_speichern(produkt_mapping_datei, mapping):
    with open(produkt_mapping_datei, "w", encoding="utf-8") as datei:
        json.dump(mapping, datei, ensure_ascii=False, indent=4)


def pdf_text_auslesen(dateiname):
    reader = PdfReader(dateiname)

    text = ""

    for seite in reader.pages:
        seiten_text = seite.extract_text()
        if seiten_text:
            text += seiten_text + "\n"

    return text

"""Erzeugt aus dem PDF-Import eines Rewe-Kassenbons die Artikelliste"""
def rewe_text_zu_artikeln(text):
    artikel_liste = []
    zeilen = text.splitlines()
    ignorieren = ['LEERG', 'EURO', 'EUR', 'SUMME', 'A=', 'B=', 'GESAMTBETRAG', 'STEUER', 'NETTO', 'BRUTTO', 'KUNDENBELEG', 'DATUM:', 'UHRZEIT:', 'BELEG-NR', 'TRACE-NR', 'BEZAHLUNG', 'CONTACTLESS', 'VISA', 'NR.', 'VU-NR', 'TERMINAL-ID', 'POS-INFO', 'AS-ZEIT', 'AS-PROC-CODE', 'CAPT.-REF', 'APPROVED', 'ZAHLUNG ERFOLGT', 'BETRAG']
    letzter_artikel = None
    for zeile in zeilen:
        zeile = zeile.strip()
        if zeile.upper().startswith(("NR.", "POS-INFO", "AS-PROC-CODE", "VU-NR", "TERMINAL-ID")):
            continue
        if 'PFAND' in zeile.upper() and '*' in zeile:
            letzter_artikel = None
        zeile = zeile.replace("*", "").strip()
        if zeile == '':
            continue
        teile = zeile.split()
        negativer_betrag = False
        for teil in teile:
            try:
                wert = float(teil.replace(',' , '.'))
                if wert < 0:
                    negativer_betrag = True
                    break
            except ValueError:
                continue
        if negativer_betrag:
            letzter_artikel = None
            continue
        if 'STK X' in zeile.upper():
            if letzter_artikel is not None:
                teile = zeile.split()
                try:
                    menge = float(teile[0].replace(',' , '.'))
                    einzelpreis = float(teile[-1].replace(',' , '.'))
                    einheit = str(teile[1]).strip()

                    letzter_artikel['menge'] = menge
                    letzter_artikel['einheit'] = einheit
                    letzter_artikel['einzelpreis'] = einzelpreis
                except (ValueError, IndexError):
                    pass
            continue
        if 'HANDEINGABE E-BON' in zeile.upper():
            if letzter_artikel is not None:
                teile = zeile.split()
                try:
                    menge = float(teile[-2].replace(',' , '.'))
                    einheit = str(teile[-1]).strip()
                    gesamtpreis = letzter_artikel['einzelpreis']
                    einzelpreis = gesamtpreis/menge

                    letzter_artikel['menge'] = menge
                    letzter_artikel['einheit'] = einheit
                    letzter_artikel['einzelpreis'] = round(einzelpreis, 2)
                except (ValueError, IndexError, ZeroDivisionError):
                    pass
            continue

        if any(wort in zeile.upper() for wort in ignorieren):
            continue
        teile = zeile.split()
        if len(teile) < 3:
            continue
        if teile[-1] not in ['A', 'B']:
            continue
        preis = None
        preis_index = None
        for i in range (len(teile) -1, -1, -1):
            preis_text = teile[i].replace(',', '.')
            try:
                preis = float(preis_text)
                preis_index = i
                break
            except ValueError:
                continue
        if preis is None:
            continue
        produkt_teile = teile[:preis_index]
        produkt = ' '.join(produkt_teile)
        if 'BIO' in produkt.upper():
            bio = 'ja'
        else:
            bio = 'unbekannt'
        
        kategorie = kategorie_vorschlagen(produkt, kategorie_zuordnung)
        
        artikel = {"produkt": produkt, "produkt_original": produkt, "produkt_standard": produkt_standard_bestimmen(produkt, mapping), "bio": bio, "kategorie": kategorie, "menge": None, "einheit": 'unbekannt', "einzelpreis": preis, "inhalt_menge": None,
"inhalt_einheit": "unbekannt", "haendler": 'Rewe', "datum": None, "kalenderwoche": None, "monat": None, "vollstaendig": False}
        artikel_liste.append(artikel)
        letzter_artikel = artikel
    return artikel_liste


def kategorie_vorschlagen (produkt, kategorie_zuordnung):
    if kategorie_zuordnung is None:
        kategorie_zuordnung = {}

    produkt_gross = produkt.upper()
    kategorie = 'unbekannt'
    for kat, woerter in kategorie_zuordnung.items():
        for wort in woerter:
            if wort in produkt_gross:
                return kat
    return 'unbekannt'


def kategorie_zuordnung_lernen(produkt, kategorie, kategorie_zuordnung):
    if kategorie == 'unbekannt':
        return kategorie_zuordnung
    if kategorie not in kategorie_zuordnung:
        kategorie_zuordnung[kategorie] = []
    if produkt.upper().strip() not in kategorie_zuordnung[kategorie]:
        while True:
            wert = input(f'Soll {produkt} künftig automatisch dieser Kategorie zugeordnet werden? (ja/nein): ').strip().lower()
            if wert == 'ja':
                kategorie_zuordnung[kategorie].append(produkt.upper().strip())
                print(f'{produkt} wurde dieser Kategorie zugeordnet.')
                return kategorie_zuordnung
            elif wert == 'nein':
                print(f'{produkt} wurde dieser Kategorie nicht zugeordnet.')
                return kategorie_zuordnung
            else:
                print("Bitte ja oder nein eingeben. ")
    return kategorie_zuordnung


def rewe_datum_aus_text(text):
    zeilen = text.splitlines()
    for zeile in zeilen:
        zeile = zeile.strip()
        
        treffer = re.search(r'\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}', zeile)
        if treffer:
            datum_zeit_text = treffer.group()
            teile = datum_zeit_text.split()
            datum_string = teile[0]
            zeit = teile[1]
            datum_objekt = datetime.strptime(datum_string, "%d.%m.%Y")
            datum = datum_objekt.strftime("%Y-%m-%d")
            kw = datum_objekt.isocalendar().week
            monat = datum_objekt.month
            return datum, zeit, kw, monat
        
    return None, None, None, None
            

def rewe_bonnummer_aus_text(text):
    treffer = re.search(r'Bon-Nr\.?:\s*(\d+)', text)
    if treffer:
        return treffer.group(1)
    return None


def rewe_pdf_import(dateiname):
    text = pdf_text_auslesen(dateiname)
    artikel_liste = rewe_text_zu_artikeln(text)
    datum, zeit, kw, monat = rewe_datum_aus_text(text)
    bonnummer = rewe_bonnummer_aus_text(text)
    bon_id = f'Rewe-{datum}-{zeit}-{bonnummer}'

    for artikel in artikel_liste:
        artikel['datum'] = datum
        artikel['zeit'] = zeit
        artikel['kalenderwoche'] = kw
        artikel['monat'] = monat
        artikel['bon_id'] = bon_id
        vollstaendigkeit_pruefen(artikel)
    return artikel_liste


def vollstaendigkeit_pruefen(artikel):
    relevante_felder = ["produkt", "bio", "kategorie", "menge", "einheit", "einzelpreis", "haendler", "datum"]
    artikel["vollstaendig"] = all(artikel.get(feld) not in [None, "", "unbekannt"] for feld in relevante_felder)
    return artikel

                
def auswahl_aus_liste(titel, optionen, stammdaten, schluessel, stammdaten_datei):
    while True:
        print(f'\n{titel}')
        for i, option in enumerate(optionen, start=1):
            print(f'{i} = {option}')
        print("0 oder x = zurück")
        print("n = neuer Eintrag")
        eingabe = (input('Auswahl: ')).strip().lower()
        if eingabe == 'x' or eingabe == '0':
                return None
        if eingabe == 'n':
            while True:
                wert = str(input("Bitte neuen Eintrag eingeben: ")).strip().title()
                if wert == '':
                    print("Eintrag darf nicht leer sein.")
                elif wert in optionen:
                    print("Der Eintrag existiert bereits.")
                else:
                    optionen.append(wert)
                    stammdaten[schluessel] = optionen
                    if schluessel == 'KATEGORIEN':
                        if wert not in stammdaten['KATEGORIE_ZUORDNUNG']:
                            stammdaten["KATEGORIE_ZUORDNUNG"][wert] = []
                    stammdaten_speichern(stammdaten_datei, stammdaten)
                    return wert
        try:
            auswahl = int(eingabe)
            if 1 <= auswahl <= len(optionen):
                return optionen[auswahl - 1]
            else:
                print(f'Bitte Zahl zwischen 1 und {len(optionen)} eingeben.')
        except ValueError:
            print('Bitte eine Zahl eingeben oder x zum Zurückgehen.')


def eingabe_mit_abbruch(text):
    wert = input(text + " (x = zurück): ").strip()
    if wert.lower() == "x":
        return None
    return wert


def zahl_eingeben(text):
    while True:
        wert = eingabe_mit_abbruch(text)
        if wert is None:
            return None
        try:
            return float(wert)
        except ValueError:
            print("Bitte die Zahl mit Punkt eingeben.")


def datum_eingeben(text):
    while True:
        wert = eingabe_mit_abbruch(text)
        if wert is None:
            return None, None, None
        try:
            datum_objekt = datetime.strptime(wert, "%d.%m.%Y")
            datum_iso = datum_objekt.strftime("%Y-%m-%d")
            kw = datum_objekt.isocalendar().week
            monat = datum_objekt.month
            return datum_iso, kw, monat
        except ValueError:
            print("Bitte Datum als TT.MM.JJJJ eingeben: ")


def eintrag_hinzufuegen(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung, mapping):
    produkt = eingabe_mit_abbruch('Produkt')
    if produkt is None:
        return einkaeufe, kategorie_zuordnung
    produkt = produkt.title()
    while True:
        bio = eingabe_mit_abbruch('Bio')
        if bio is None:
            return einkaeufe, kategorie_zuordnung
        bio = bio.lower()
        if bio in ['ja', 'nein']:
            break
        else:
            print("Bitte 'ja' oder 'nein' eingeben.")
    kategorie = auswahl_aus_liste( "Kategorie auswählen:", kategorien_liste, stammdaten, "KATEGORIEN", stammdaten_datei)
    if kategorie is None:
        return einkaeufe, kategorie_zuordnung
    kategorie_zuordnung = kategorie_zuordnung_lernen(produkt, kategorie, kategorie_zuordnung)
    menge = zahl_eingeben('Menge')
    if menge is None:
        return einkaeufe, kategorie_zuordnung
    einheit = auswahl_aus_liste( "Einheit auswählen:", einheiten_liste, stammdaten, "EINHEITEN", stammdaten_datei)
    if einheit is None:
        return einkaeufe, kategorie_zuordnung
    preis_pro_einheit = zahl_eingeben('Einzelpreis')
    if preis_pro_einheit is None:
        return einkaeufe, kategorie_zuordnung
    haendler = auswahl_aus_liste("Händler auswählen:", haendler_liste, stammdaten, "HAENDLER", stammdaten_datei)
    if haendler is None:
        return einkaeufe, kategorie_zuordnung
    datum_iso, kw, monat = datum_eingeben('Datum')
    if datum_iso is None:
        return einkaeufe, kategorie_zuordnung
    vollstaendig = True
    
    artikel = {"produkt": produkt, "produkt_original": produkt, "produkt_standard": produkt_standard_bestimmen(produkt, mapping), "bio": bio, "kategorie": kategorie, "menge": menge, "einheit": einheit, "einzelpreis": preis_pro_einheit, "inhalt_menge": None,
"inhalt_einheit": "unbekannt", "haendler": haendler, "datum": datum_iso, "kalenderwoche": kw, "monat": monat, "vollstaendig": vollstaendig}
    vollstaendigkeit_pruefen(artikel)

    einkaeufe.append(artikel)
    return einkaeufe, kategorie_zuordnung


def schnellerfassung(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung, mapping):
    produkt = eingabe_mit_abbruch('Produkt')
    if produkt is None:
        return einkaeufe, kategorie_zuordnung
    produkt = produkt.title()
    preis_pro_einheit = zahl_eingeben('Einzelpreis')
    if preis_pro_einheit is None:
        return einkaeufe, kategorie_zuordnung
    haendler = auswahl_aus_liste("Händler auswählen:", haendler_liste, stammdaten, "HAENDLER", stammdaten_datei)
    if haendler is None:
        return einkaeufe, kategorie_zuordnung
    datum_iso, kw, monat = datum_eingeben('Datum')
    if datum_iso is None:
        return einkaeufe, kategorie_zuordnung
    bio = 'unbekannt'
    kategorie = kategorie_vorschlagen (produkt, kategorie_zuordnung)
    if kategorie == "unbekannt":
        print("Keine Kategorie automatisch erkannt.")
        kategorie = auswahl_aus_liste( "Kategorie auswählen:", kategorien_liste, stammdaten, "KATEGORIEN", stammdaten_datei)
        if kategorie is None:
            return einkaeufe, kategorie_zuordnung
    else:
        print(f"Vorgeschlagene Kategorie: {kategorie}")
    kategorie_zuordnung = kategorie_zuordnung_lernen(produkt, kategorie, kategorie_zuordnung)
    menge = None
    einheit = 'unbekannt'
    vollstaendig = False
    
    artikel = {"produkt": produkt, "produkt_original": produkt, "produkt_standard": produkt_standard_bestimmen(produkt, mapping), "bio": bio, "kategorie": kategorie, "menge": menge, "einheit": einheit, "einzelpreis": preis_pro_einheit, "inhalt_menge": None,
"inhalt_einheit": "unbekannt", "haendler": haendler, "datum": datum_iso, "kalenderwoche": kw, "monat": monat, 'vollstaendig': vollstaendig}
    
    einkaeufe.append(artikel)
    return einkaeufe, kategorie_zuordnung


def eintrag_vervollstaendigen(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return einkaeufe, kategorie_zuordnung
    gefunden = False
    for artikel in einkaeufe:
        if not isinstance(artikel, dict):
            continue
        if not artikel["vollstaendig"]:
            gefunden = True
    if not gefunden:
        print("Keine unvollständigen Einträge vorhanden.")
        return einkaeufe, kategorie_zuordnung
    eintraege_unvollstaendig = []
    for artikel in einkaeufe:
        if not artikel["vollstaendig"]:
            eintraege_unvollstaendig.append(artikel)
    for i, artikel in enumerate(eintraege_unvollstaendig, start=1):
        print(f"{i}: {artikel['datum']} | {artikel['produkt']} | {artikel['bio']} | {artikel['kategorie']} | {artikel['menge']} {artikel['einheit']} | {artikel['einzelpreis']:.2f} € | {artikel['haendler']}")
        print("-" * 100)
    while True:
        try:
            auswahl = eingabe_mit_abbruch('Nummer des Eintrags: ')
            if auswahl is None:
                return einkaeufe, kategorie_zuordnung
            auswahl = int(auswahl)
            if 1 <= auswahl <= len(eintraege_unvollstaendig):
                index = auswahl - 1
                eintrag_auswahl = eintraege_unvollstaendig[index]
                if 'produkt_original' not in eintrag_auswahl:
                    eintrag_auswahl['produkt_original'] = eintrag_auswahl['produkt']
                if 'produkt_standard' not in eintrag_auswahl:
                    eintrag_auswahl['produkt_standard'] = eintrag_auswahl['produkt']
                if 'inhalt_menge' not in eintrag_auswahl:
                    eintrag_auswahl['inhalt_menge'] = None
                if 'inhalt_einheit' not in eintrag_auswahl:
                    eintrag_auswahl['inhalt_einheit'] = "unbekannt"
                if eintrag_auswahl['bio'] == 'unbekannt':
                    while True:
                        bio = eingabe_mit_abbruch('Bio')
                        if bio is None:
                            break
                        bio = bio.lower()
                        if bio in ['ja', 'nein']:
                            eintrag_auswahl['bio'] = bio
                            break
                        else:
                            print("Bitte 'ja' oder 'nein' eingeben.")
                if eintrag_auswahl['kategorie'] == 'unbekannt':
                    kategorie = auswahl_aus_liste( "Kategorie auswählen:", kategorien_liste, stammdaten, "KATEGORIEN", stammdaten_datei)
                    if kategorie is None:
                        continue
                    eintrag_auswahl['kategorie'] = kategorie
                    kategorie_zuordnung = kategorie_zuordnung_lernen(eintrag_auswahl['produkt'], eintrag_auswahl['kategorie'], kategorie_zuordnung)
                else:
                    print(f"Kategorie: {eintrag_auswahl['kategorie']} (übernommen)")
                if eintrag_auswahl['menge'] == None:
                    menge = zahl_eingeben('Menge')
                    if menge is None:
                        continue
                    eintrag_auswahl['menge'] = menge
                if eintrag_auswahl['einheit'] == 'unbekannt':
                    einheit = auswahl_aus_liste( "Einheit auswählen:", einheiten_liste, stammdaten, "EINHEITEN", stammdaten_datei)
                    if einheit is None:
                        continue
                    eintrag_auswahl['einheit'] = einheit 
                vollstaendigkeit_pruefen(eintrag_auswahl)
                return einkaeufe, kategorie_zuordnung
            else:
                print(f"Bitte Zahl zwischen 1 und {len(eintraege_unvollstaendig)} eingeben.")
        except ValueError:
            print("Bitte eine Zahl eingeben.")
    return einkaeufe, kategorie_zuordnung
    

def eintrag_bearbeiten(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return einkaeufe, kategorie_zuordnung
    eintraege_vollstaendig = []
    for artikel in einkaeufe:
        if not isinstance(artikel, dict):
            continue
        if artikel["vollstaendig"]:
            eintraege_vollstaendig.append(artikel)
    if not eintraege_vollstaendig:
        print("Keine vollständigen Einträge vorhanden.")
        return einkaeufe, kategorie_zuordnung
    for i, artikel in enumerate(eintraege_vollstaendig, start=1):
        print(f"{i}: {artikel['datum']} | {artikel['produkt']} | {artikel['bio']} | {artikel['kategorie']} | {artikel['menge']} {artikel['einheit']} | {artikel['einzelpreis']:.2f} € | {artikel['haendler']}")
        print("-" * 100)
    while True:
        try:
            auswahl = eingabe_mit_abbruch('Nummer des Eintrags: ')
            if auswahl is None:
                return einkaeufe, kategorie_zuordnung
            auswahl = int(auswahl)
            if 1 <= auswahl <= len(eintraege_vollstaendig):
                index = auswahl - 1
                eintrag_auswahl = eintraege_vollstaendig[index]
                while True:
                    print('1 = Produkt ändern: ')
                    print('2 = Bio ändern')
                    print('3 = Kategorie ändern')
                    print('4 = Menge ändern')
                    print('5 = Einheit ändern')
                    print('6 = Einzelpreis ändern')
                    print('7 = Händler ändern')
                    print('8 = Kaufdatum ändern')
                    print('9 = Bearbeitung beenden')

                    wahl = input('Auswahl: ').strip()
                    if wahl == '1':
                        produkt = eingabe_mit_abbruch('Produkt')
                        if produkt is None:
                            continue
                        produkt = produkt.title()
                        while True:
                            wert = input(f'Soll {produkt} auch der Standardname sein? ja/nein: ').strip().lower()
                            if wert == 'ja':
                                eintrag_auswahl['produkt_standard'] = produkt
                                break
                            elif wert == 'nein':
                                break
                            else:
                                print("Bitte ja oder nein eingeben.")
                        eintrag_auswahl['produkt'] = produkt
                        eintrag_auswahl['produkt_original'] = produkt
                    elif wahl == '2':
                        while True:
                            bio = eingabe_mit_abbruch('Bio')
                            if bio is None:
                                break
                            bio = bio.lower()
                            if bio in ['ja', 'nein']:
                                eintrag_auswahl['bio'] = bio
                                break
                            else:
                                print("Bitte 'ja' oder 'nein' eingeben.")
                    elif wahl == '3':
                        kategorie = auswahl_aus_liste( "Kategorie auswählen:", kategorien_liste, stammdaten, "KATEGORIEN", stammdaten_datei)
                        if kategorie is None:
                            continue
                        eintrag_auswahl['kategorie'] = kategorie
                        kategorie_zuordnung = kategorie_zuordnung_lernen(eintrag_auswahl['produkt'], eintrag_auswahl['kategorie'], kategorie_zuordnung)
                    elif wahl == '4':
                        menge = zahl_eingeben('Menge')
                        if menge is None:
                            continue
                        eintrag_auswahl['menge'] = menge
                    elif wahl == '5':
                        einheit = auswahl_aus_liste( "Einheit auswählen:", einheiten_liste, stammdaten, "EINHEITEN", stammdaten_datei)
                        if einheit is None:
                            continue
                        eintrag_auswahl['einheit'] = einheit
                    elif wahl == '6':
                        einzelpreis = zahl_eingeben('Einzelpreis')
                        if einzelpreis is None:
                            continue
                        eintrag_auswahl['einzelpreis'] = einzelpreis
                    elif wahl == '7':
                        haendler = auswahl_aus_liste("Händler auswählen:", haendler_liste, stammdaten, "HAENDLER", stammdaten_datei)
                        if haendler is None:
                            continue
                        eintrag_auswahl['haendler'] = haendler
                    elif wahl == '8':
                        datum_iso, kw, monat = datum_eingeben('Datum')
                        if datum_iso is None:
                            continue
                        eintrag_auswahl['kalenderwoche'] = kw
                        eintrag_auswahl['monat'] = monat
                        eintrag_auswahl['datum'] = datum_iso
                    elif wahl == '9':
                        return einkaeufe, kategorie_zuordnung
                    else:
                        print('Bitte Zahl zwischen 1 und 9 eingeben.')
        except ValueError:
            print("Bitte eine Zahl eingeben.")
    return einkaeufe, kategorie_zuordnung
    
    
def eintrag_loeschen(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return einkaeufe
    for i, artikel in enumerate(einkaeufe, start=1):
        print(f"{i}: {artikel['datum']} | {artikel['produkt']} | {artikel['bio']} | {artikel['kategorie']} | {artikel['menge']} {artikel['einheit']} | {artikel['einzelpreis']:.2f} € | {artikel['haendler']}")
        print("-" * 100)
    while True:
        try:
            auswahl = eingabe_mit_abbruch('Nummer des Eintrags')
            if auswahl is None:
                return einkaeufe
            auswahl = int(auswahl)
            if 1 <= auswahl <= len(einkaeufe):
                index = auswahl - 1
                loescheintrag = einkaeufe[index]
                print('Sie löschen: \n')
                print(f"{auswahl}: {loescheintrag['datum']} | {loescheintrag['produkt']} | {loescheintrag['bio']} | {loescheintrag['kategorie']} | {loescheintrag['menge']} {loescheintrag['einheit']} | {loescheintrag['einzelpreis']:.2f} € | {loescheintrag['haendler']}")
                while True:
                    sicherheitsfrage = eingabe_mit_abbruch('Wollen Sie den Eintrag wirklich löschen? Ja / Nein')
                    if sicherheitsfrage is None:
                        break
                    sicherheitsfrage = sicherheitsfrage.lower()
                    if sicherheitsfrage == 'ja':
                        del einkaeufe[index]
                        print(f'Der Eintrag mit der Nummer {auswahl} wurde gelöscht.')
                        return einkaeufe
                    elif sicherheitsfrage == 'nein':
                        print('Eintrag löschen wurde abgebrochen.')
                        return einkaeufe
                    else:
                        print('Bitte ja oder nein eingeben.')
            else:
                print(f'Bitte eine Zahl zwischen 1 und {len(einkaeufe)} eingeben.')
        except ValueError:
            print("Bitte eine Zahl eingeben.")
    return einkaeufe
    

def alle_einkaeufe_anzeigen(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
##        print('Es wurden folgende Artikel gekauft:\n')
    print('Alle vollständigen Einträge\n')
    for artikel in sorted(einkaeufe, key=lambda x: x['datum']):
        if artikel['vollstaendig']:
            print(f"{artikel['datum']} | {artikel['produkt']} | {artikel['bio']} | {artikel['kategorie']} | {artikel['menge']} {artikel['einheit']} | {artikel['einzelpreis']:.2f} € | {artikel['haendler']}")
            print("-" * 100 + '\n')
    print('Alle unvollständigen Einträge\n')
    for artikel in sorted(einkaeufe, key=lambda x: x['datum']):
        if not artikel['vollstaendig']:
            print(f"{artikel['datum']} | {artikel['produkt']} | {artikel['einzelpreis']:.2f} € | {artikel['haendler']}")
            print("-" * 100 + '\n')
            
        
def unvollstaendige_einkaeufe_anzeigen(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    print("Folgende Einträge sind unvollständig und müssen bearbeitet werden:\n")
    gefunden = False
    for artikel in sorted(einkaeufe, key=lambda x: x['datum']):
        if not artikel['vollstaendig']:
            print(f"{artikel['datum']} | {artikel['produkt']} | {artikel['bio']} | {artikel['kategorie']} | {artikel['menge']} {artikel['einheit']} | {artikel['einzelpreis']:.2f} € | {artikel['haendler']} | {artikel['vollstaendig']}")
            print("-" * 100)
            gefunden = True
    if not gefunden:
        print("Alle Einträge sind vollständig und können ausgewertet werden.")
                                

def kategorie_uebersicht(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    kategorie_daten = {}
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            kategorie = artikel['kategorie']
            menge = artikel['menge']
            kosten = menge * artikel['einzelpreis']
            if kategorie in kategorie_daten:
                kategorie_daten[kategorie] += kosten
            else:
                kategorie_daten[kategorie] = kosten
    for kategorie, kosten in sorted(kategorie_daten.items()):
        print(f"{kategorie} | {kosten:.2f} € ")
        print("-" * 40)

        
def produkt_uebersicht(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    produkt_daten = {}
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            produkt = artikel['produkt']
            menge = artikel['menge']
            einheit = artikel['einheit']
            kosten = menge * artikel['einzelpreis']
            if produkt in produkt_daten:
                produkt_daten[produkt]['menge'] += menge
                produkt_daten[produkt]['kosten'] += kosten
            else:
                produkt_daten[produkt] = {'menge': menge, 'einheit': einheit, 'kosten': kosten}
    for produkt, daten in sorted(produkt_daten.items()):
        print(f"{produkt} | {daten['menge']} {daten['einheit']} | {daten['kosten']:.2f} € ")
        print("-" * 40)


def monat_uebersicht(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    monat_daten = {}
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            monat = artikel['monat']
            menge = artikel['menge']
            kosten = menge * artikel['einzelpreis']
            if monat in monat_daten:
                monat_daten[monat] += kosten
            else:
                monat_daten[monat] = kosten
    if not monat_daten:
        print("Keine vollständigen Einträge für die Monatsübersicht vorhanden.")
        return
    for monat, kosten in sorted(monat_daten.items()):
        print(f"Monat {monat} | {kosten:.2f} € ")
        print("-" * 40)


def woche_uebersicht(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    woche_daten = {}
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            woche = artikel['kalenderwoche']
            menge = artikel['menge']
            kosten = menge * artikel['einzelpreis']
            if woche in woche_daten:
                woche_daten[woche] += kosten
            else:
                woche_daten[woche] = kosten
    if not woche_daten:
        print("Keine vollständigen Einträge für die Wochenübersicht vorhanden.")
        return
    for woche, kosten in sorted(woche_daten.items()):
        print(f"Kalenderwoche {woche} | {kosten:.2f} € ")
        print("-" * 40)
        
        
def gesamtbetrag(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    gesamt = 0
    gefunden = False
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            gefunden = True
            gesamt += artikel['menge'] * artikel['einzelpreis']
    gesamt = round(gesamt, 2)
    if not gefunden:
        print("Keine vollständigen Einträge für den Gesamtbetrag vorhanden.")
        return
    print(f"Der Gesamtbetrag für alle vollständigen Artikel beträgt: {gesamt:.2f} €")


def menue_erfassung(dateiname, einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung):
    while True:
        print('\n' + '=' * 50)
        print('Einträge erfassen')
        print('=' * 50)
        print('1 = vollständigen Eintrag hinzufügen')
        print('2 = schnellen Eintrag hinzufügen')
        print('3 = Rewe Kassenbon importieren')
        print('9 = zurück zum Hauptmenü')

        wahl = input('Menü-Auswahl: ').strip()

        if wahl == '1':
            einkaeufe, kategorie_zuordnung = eintrag_hinzufuegen(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung, mapping)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            daten_speichern(dateiname, einkaeufe)
        elif wahl == '2':
            einkaeufe, kategorie_zuordnung = schnellerfassung(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung, mapping)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            daten_speichern(dateiname, einkaeufe)
            produkt_mapping_speichern(produkt_mapping_datei, mapping)
        elif wahl == '3':
            pdf_dateiname = eingabe_mit_abbruch('PDF-Dateiname: ')
            if pdf_dateiname is None:
                continue
            neue_artikel = rewe_pdf_import(pdf_dateiname)
            if neue_artikel:
                neue_bon_id = neue_artikel[0].get('bon_id')
                if neue_bon_id is None:
                    print("Keine Bon-ID erkannt. Der Import kann nicht auf Duplikate geprüft werden.")
                if any(artikel.get('bon_id') == neue_bon_id for artikel in einkaeufe):
                    print("Dieser Bon wurde bereits importiert.")
                    continue
            print(f'{len(neue_artikel)} Artikel wurden importiert.')
            alle_einkaeufe_anzeigen(neue_artikel)
            produkt_mapping_ergaenzen(neue_artikel, mapping)
            einkaeufe.extend(neue_artikel)
            daten_speichern(dateiname, einkaeufe)
            produkt_mapping_speichern(produkt_mapping_datei, mapping)

        elif wahl == '9':
            return einkaeufe, kategorie_zuordnung
        else:
            print('Fehlerhafte Eingabe.')
            
            
def menue_bearbeiten(dateiname, einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung):
    while True:
        print('\n' + '=' * 50)
        print('Einträge bearbeiten')
        print('=' * 50)
        print('1 = Eintrag bearbeiten')
        print('2 = unvollständigen Eintrag vervollständigen')
        print('3 = Eintrag löschen')
        print('9 = zurück zum Hauptmenü')
        
        wahl = input('Menü-Auswahl: ').strip()
        if wahl == '1':
            einkaeufe, kategorie_zuordnung = eintrag_bearbeiten(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            daten_speichern(dateiname, einkaeufe)
        elif wahl == '2':
            einkaeufe, kategorie_zuordnung = eintrag_vervollstaendigen(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            daten_speichern(dateiname, einkaeufe)
        elif wahl == '3':
            einkaeufe = eintrag_loeschen(einkaeufe)
            daten_speichern(dateiname, einkaeufe)
        elif wahl == '9':
            return einkaeufe, kategorie_zuordnung
        else:
            print('Fehlerhafte Eingabe.')
    
        
def menue_auswertungen(einkaeufe):
    while True:
        print('\n' + '=' * 50)
        print('Auswertungen')
        print('=' * 50)
        print('1 = alle Einkäufe anzeigen')
        print('2 = unvollständige Einträge anzeigen')
        print('3 = Gesamtbetrag')
        print('4 = Produktübersicht')
        print('5 = Kategorieübersicht')
        print('6 = Monatsübersicht')
        print('7 = Wochenübersicht')
        print('9 = zurück zum Hauptmenü')
        
        wahl = input('Menü-Auswahl: ').strip()
                
        if wahl == '1':
            alle_einkaeufe_anzeigen(einkaeufe)
        elif wahl == '2':
            unvollstaendige_einkaeufe_anzeigen(einkaeufe)
        elif wahl == '3':
            gesamtbetrag(einkaeufe)
        elif wahl == '4':
            produkt_uebersicht(einkaeufe)
        elif wahl == '5':
            kategorie_uebersicht(einkaeufe)
        elif wahl == '6':
            monat_uebersicht(einkaeufe)
        elif wahl == '7':
            woche_uebersicht(einkaeufe)
        elif wahl == '9':
            return
        else:
            print('Fehlerhafte Eingabe.')
    

# ------------------------
# Hauptprogramm (Menü)
# ------------------------


dateiname = "einkaeufe.json"
stammdaten_datei = "stammdaten.json"
produkt_mapping_datei = "produkt_mapping.json"

stammdaten = stammdaten_laden(stammdaten_datei)
mapping = produkt_mapping_laden(produkt_mapping_datei)

kategorien_liste = stammdaten.get("KATEGORIEN", [])
haendler_liste = stammdaten.get("HAENDLER", [])
einheiten_liste = stammdaten.get("EINHEITEN", [])
kategorie_zuordnung = stammdaten.get("KATEGORIE_ZUORDNUNG", {})
if not isinstance(kategorie_zuordnung, dict):
    kategorie_zuordnung = {}
einkaeufe = daten_laden(dateiname)

while True:
    print('\n' + '=' * 50)
    print('Einkaufsprotokoll')
    print('=' * 50)
    print('1 = Erfassung')
    print('2 = Bearbeitung')
    print('3 = Auswertungen')
    print('9 = Programm beenden')

    wahl = input('Menü-Auswahl: ').strip()

    if wahl == '1':
        einkaeufe, kategorie_zuordnung = menue_erfassung(dateiname, einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung)
    elif wahl == '2':
        einkaeufe, kategorie_zuordnung = menue_bearbeiten(dateiname, einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung)
    elif wahl == '3':
        menue_auswertungen(einkaeufe)
    elif wahl == '9':
        daten_speichern(dateiname, einkaeufe)
        print('Programm beendet.')
        break
    else:
        print('Fehlerhafte Eingabe.')
