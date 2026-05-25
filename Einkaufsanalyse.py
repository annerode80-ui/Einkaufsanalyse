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
import re
import unicodedata
import pytesseract
from datetime import datetime
from pypdf import PdfReader
from PIL import Image
from PIL import ImageEnhance
from pathlib import Path

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

        if 'inhalt_einheit' not in artikel or str(artikel['inhalt_einheit']).strip() == '':
            artikel['inhalt_einheit'] = 'unbekannt'

        if 'bio' not in artikel or artikel['bio'] not in ['ja', 'nein']:
            artikel['bio'] = 'unbekannt'

        if 'menge' not in artikel or artikel['menge'] is None or artikel['menge'] == '':
            artikel['menge'] = None

        if 'inhalt_menge' not in artikel or artikel['inhalt_menge'] is None or artikel['inhalt_menge'] == '':
            artikel['inhalt_menge'] = None

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

""" Speichert alle Einkäufe als JSON-Datei. Parameter: einkaeufe: Liste von Artikel-Dictionaries """
def daten_speichern(dateiname, einkaeufe):
    with open(dateiname, "w", encoding="utf-8") as datei:
        json.dump(einkaeufe, datei, ensure_ascii=False, indent=4)

"""Lädt Stammdaten (Kategorien, Händler, Einheiten, Zuordnungen) aus JSON-Datei."""
def stammdaten_laden(dateiname):
    try:
        with open(dateiname, "r", encoding="utf-8") as datei:
            stammdaten = json.load(datei)
            stammdaten['EINHEITEN'] = [text_normalisieren(wert)
            for wert in stammdaten['EINHEITEN']]
            stammdaten['KATEGORIEN'] = [text_normalisieren(wert)
            for wert in stammdaten['KATEGORIEN']]
            stammdaten['HAENDLER'] = [text_normalisieren(wert)
            for wert in stammdaten['HAENDLER']]
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


def produkt_stammdaten_laden(dateiname):
    try:
        with open(dateiname, "r", encoding="utf-8") as datei:
            produkt_stammdaten = json.load(datei)
            return produkt_stammdaten
    except FileNotFoundError:
        print("Produkt-Stammdaten-Datei nicht gefunden.")
        return {}
    except json.JSONDecodeError:
        print("Produkt-Stammdaten-Datei ist fehlerhaft.")
        return {}


def produkt_stammdaten_aus_artikel(artikel):
    produkt_stammdaten = {
        'produkt_standard': artikel['produkt_standard'], 
        'bio': artikel['bio'], 
        'kategorie': artikel['kategorie'], 
        'inhalt_menge': artikel['inhalt_menge'], 
        'inhalt_einheit': artikel['inhalt_einheit']
        }
    return produkt_stammdaten


def produkt_stammdaten_lernen(artikel, produkt_stammdaten):
    produkt_stammdaten[artikel['produkt_original']] = produkt_stammdaten_aus_artikel(artikel)
    return produkt_stammdaten


def produkt_stammdaten_aus_vollstaendigen_artikeln_lernen(einkaeufe, produkt_stammdaten):
    gelernt = 0
    for artikel in einkaeufe:
        vollstaendigkeit_pruefen(artikel)
        if artikel['vollstaendig']:
            produkt_stammdaten = produkt_stammdaten_lernen(artikel, produkt_stammdaten)
            gelernt += 1
    print(f'Es wurden {gelernt} Artikel in die Produkt-Stammdaten aufgenommen.')
    return produkt_stammdaten


def produkt_stammdaten_anwenden(artikel, produkt_stammdaten):
    produkt_original = artikel.get('produkt_original')
    if produkt_original not in produkt_stammdaten:
        return artikel
    stammdaten = produkt_stammdaten[produkt_original]
    for feld, wert in stammdaten.items():
        if artikel.get(feld) in [None, "", "unbekannt"]:
            artikel[feld] = wert
    vollstaendigkeit_pruefen(artikel)
    return artikel


def produkt_stammdaten_speichern(dateiname, produkt_stammdaten):
    with open(dateiname, "w", encoding="utf-8") as datei:
        json.dump(produkt_stammdaten, datei, ensure_ascii=False, indent=4)

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


def produkt_inhalte_laden(dateiname):
    try:
        with open(dateiname, "r", encoding="utf-8") as datei:
             inhalte = json.load(datei)
             return inhalte
    except FileNotFoundError:
        print("Hinweis: produkt_inhalte.json nicht gefunden – wird neu erstellt.")
        return {}
    except json.JSONDecodeError:
        print("Fehler: produkt_inhalte.json ist beschädigt.")
        return {}


def produkt_inhalte_bestimmen(produkt, inhalte):
    if produkt in inhalte:
        return inhalte[produkt]
    return {'inhalt_menge': None, 'inhalt_einheit': 'unbekannt'}


def produkt_inhalte_ergaenzen(artikel_liste, inhalte, einheiten_liste):
    bearbeitet = set()
    for artikel in artikel_liste:
        if artikel['inhalt_menge'] == None and artikel ['inhalt_einheit'] == 'unbekannt' and artikel['produkt_original']not in bearbeitet:
            produkt_original = artikel['produkt_original']
            menge_text = input(
                f'Bitte die enthaltene Menge für "{artikel["produkt_original"]}" eingeben (Enter = Artikel überspringen): '
            ).strip()
            if menge_text == '':
                bearbeitet.add(artikel['produkt_original'])
                continue
            try:
                menge = float(menge_text.replace(',', '.'))
            except ValueError:
                print("Menge konnte nicht gelesen werden. Artikel wird übersprungen.")
                bearbeitet.add(produkt_original)
                continue
            einheit = auswahl_aus_liste (
                f"Einheit der enthaltenen Menge für '{artikel['produkt_original']}' auswählen:",
                  einheiten_liste,
                  stammdaten,
                  "EINHEITEN",
                  stammdaten_datei)
            if einheit is None:
                bearbeitet.add(artikel['produkt_original'])
                continue

            artikel['inhalt_menge'] = menge
            artikel['inhalt_einheit'] = einheit
            inhalte[produkt_original] = {'inhalt_menge': menge, 'inhalt_einheit': einheit}
            
            bearbeitet.add(artikel['produkt_original'])

    return artikel_liste, inhalte, einheiten_liste


def produkt_inhalte_speichern(produkt_inhalte_datei, inhalte):
    with open(produkt_inhalte_datei, "w", encoding="utf-8") as datei:
        json.dump(inhalte, datei, ensure_ascii=False, indent=4)


def text_normalisieren(text):
    if isinstance(text, str):
        return unicodedata.normalize("NFC", text).strip()
    return text





def pdf_text_auslesen(dateiname):
    reader = PdfReader(dateiname)

    text = ""

    for seite in reader.pages:
        seiten_text = seite.extract_text()
        if seiten_text:
            text += seiten_text + "\n"

    return text


"""Erzeugt aus dem PDF-Import eines Rewe-Kassenbons die Artikelliste"""
def rewe_artikel_aus_text(text, mapping, inhalte):
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
#                    einheit = str(teile[1]).strip()

                    letzter_artikel['menge'] = menge
#                    letzter_artikel['einheit'] = einheit
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

                    letzter_artikel['menge'] = menge
                    letzter_artikel['einheit'] = einheit
                    letzter_artikel['inhalt_menge'] = menge
                    letzter_artikel['inhalt_einheit'] = einheit
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
        inhalt = produkt_inhalte_bestimmen(produkt, inhalte)
        kategorie = kategorie_vorschlagen(produkt, kategorie_zuordnung)
        
        artikel = {"produkt": produkt, "produkt_original": produkt, "produkt_standard": produkt_standard_bestimmen(produkt, mapping), "bio": bio, "kategorie": kategorie, "menge": None, "einheit": 'unbekannt', "einzelpreis": preis, "inhalt_menge": inhalt['inhalt_menge'],
"inhalt_einheit": inhalt['inhalt_einheit'], "haendler": 'Rewe', "datum": None, "kalenderwoche": None, "monat": None, "vollstaendig": False}
        artikel_liste.append(artikel)
        letzter_artikel = artikel
    return artikel_liste, mapping, inhalte


def lidl_png_import(dateiname, mapping, inhalte):
    text = bild_text_auslesen(dateiname)
    relevante_zeilen = lidl_Vorfilter(text)
    artikel_liste, mapping, inhalte = lidl_parser(relevante_zeilen, mapping, inhalte)
    datum, zeit, kw, monat = rewe_datum_aus_text(text)
    bonnummer = lidl_bonnummer_aus_text(text)
    bonnummer = bonnummer_pruefen_und_bearbeiten(bonnummer)
    bon_id = f'Lidl-{datum}-{zeit}-{bonnummer}'
    for artikel in artikel_liste:
        artikel['datum'] = datum
        artikel['zeit'] = zeit
        artikel['kalenderwoche'] = kw
        artikel['monat'] = monat
        artikel['bon_id'] = bon_id
        vollstaendigkeit_pruefen(artikel)
    return text, bonnummer, artikel_liste, mapping, inhalte


def bild_text_auslesen(dateiname):
    bild = Image.open(dateiname)
    bild = bild.resize((bild.width * 3, bild.height * 3), Image.LANCZOS)
    bild = bild.convert("L")
    kontrast = ImageEnhance.Contrast(bild)
    bild = kontrast.enhance(2)
    bild = bild.point(lambda x: 0 if x < 140 else 255, '1')
    text = pytesseract.image_to_string(bild, lang='deu', config="--psm 6")
    return text


def lidl_bonnummer_aus_text(text):
    treffer = re.search(r'Beleg-Nr\.?\s*(\d+)', text, re.IGNORECASE)
    if treffer:
        bonnummer = treffer.group(1)
        if len(bonnummer) != 4:
            print("Bon-ID länger/kürzer als 4 Ziffern. Bitte prüfen.")
        return bonnummer
    return None


def bonnummer_pruefen_und_bearbeiten(bonnummer):
    if bonnummer is None:
        return None
    if len(bonnummer) == 4:
        return bonnummer
    print(f"Bonnummer wirkt auffällig: {bonnummer}")
    eingabe = input("Enter = übernehmen oder korrigierte Bonnummer eingeben: ").strip()
    if eingabe == "":
        return bonnummer
    return eingabe


def geldbetrag_aus_text(text):
    return float(text.replace(",", "."))


def lidl_bonvergleich_ausgeben(artikel_liste, text):
    treffer_zahlbetrag = re.search(r'zu zahlen\s*(\d+,\d{2})', text, re.IGNORECASE)
    treffer_gesamtrabatt = re.search(r'Gesamter Preisvorteil\s*(\d+,\d{2})', text, re.IGNORECASE)
    treffer_lidl_plus_rabatt = re.search(r'Mit Lidl Plus\s*(\d+,\d{2})\s*EUR\s*gespart', text, re.IGNORECASE)
    if treffer_zahlbetrag:
        zahlbetrag_bon = treffer_zahlbetrag.group(1)
    if treffer_gesamtrabatt:
        gesamtrabatt_bon = treffer_gesamtrabatt.group(1)
    if treffer_lidl_plus_rabatt:
        lidl_plus_bon = treffer_lidl_plus_rabatt.group(1)

    zahlbetrag_bon = geldbetrag_aus_text(treffer_zahlbetrag.group(1)) if treffer_zahlbetrag else 0.00
    gesamtrabatt_bon = geldbetrag_aus_text(treffer_gesamtrabatt.group(1)) if treffer_gesamtrabatt else 0.00
    lidl_plus_bon = geldbetrag_aus_text(treffer_lidl_plus_rabatt.group(1)) if treffer_lidl_plus_rabatt else 0.00

    summe_preise = 0
    rabatt = 0
    summe_lidl_plus_rabatt = 0
    summe_aktionsrabatt = 0

    for artikel in artikel_liste:
        summe_preise += artikel['einzelpreis']
        rabatt += artikel.get('rabatt', 0)
        for rabatt_text in artikel.get("rabatt_rohtexte", []):
            if "lidl plus" in rabatt_text.lower():
                summe_lidl_plus_rabatt += 1
            elif "aktionsrabatt" in rabatt_text.lower():
                summe_aktionsrabatt += 1
    
    errechneter_zahlbetrag = summe_preise - rabatt

    print(f"Der ausgelesene Zahlbetrag ist: {zahlbetrag_bon:.2f} €.")
    print(f"Der errechnete Zahlbetrag ist: {errechneter_zahlbetrag:.2f} €.")
    if zahlbetrag_bon is not None:
        print(f"Differenz: {zahlbetrag_bon - errechneter_zahlbetrag:.2f} €")
    if gesamtrabatt_bon is not None:
        print(f"Ausgelesener Gesamtrabatt: {gesamtrabatt_bon:.2f} €")
    if lidl_plus_bon is not None:
        print(f"Ausgelesener Lidl-Plus-Rabatt: {lidl_plus_bon:.2f} €")
    print(f"Errechneter Gesamtrabatt: {rabatt:.2f} €")
    return None


def lidl_Vorfilter(text):
    relevante_zeilen = []
    zeilen = text.splitlines()
    for zeile in zeilen:
        zeile = zeile.strip()
        zeile_klein = zeile.lower()
        if 'pfand' in zeile_klein:
            continue
        if 'ZU ZAHLEN' in zeile_klein:
            break
        if 'kg x' in zeile_klein:
            relevante_zeilen.append(zeile)
        elif 'rabatt' in zeile_klein:
            relevante_zeilen.append(zeile)
        elif zeile.endswith((' A', ' B')):
            relevante_zeilen.append(zeile)    
    return relevante_zeilen


def rabatt_aus_text_lesen(rabatt_text, artikelpreis):
    text = rabatt_text.replace("€", "").strip()
    # typische OCR-Fehler vor dem Komma
    if text.startswith("-08"):
        text = text.replace("-08", "-0", 1)
    elif text.startswith("-8"):
        text = text.replace("-8", "-0", 1)
    elif text.startswith("-9"):
        text = text.replace("-9", "-0", 1)
    elif text.startswith("-19"):
        text = text.replace("-19", "-0,19", 1)
    elif text.startswith("-50"):
        text = text.replace("-50", "-0,50", 1)
    elif text.startswith("-56"):
        text = text.replace("-56", "-0,56", 1)
    try:
        rabatt = abs(float(rabatt_text.replace(",", ".")))
    except ValueError:
        return 0
    if rabatt > artikelpreis:
        return 0
    return rabatt


def lidl_menge_aus_artikelzeile(zeile):
    treffer = re.search(r"(?<![a-zäöüß])[x×]\s*(\d+)", zeile.lower())
    if treffer:
        return float(treffer.group(1))
    return 1.0


def zahl_ocr_risiko(text): #findet OCR-risikobehaftete Zahlen
    text = str(text)
    for zeichen in [ "8"]:
        if zeichen in text:
            return True
    return False


def ocr_pruefung_artikel(artikel): # trägt alle risikobehafteten Fälle zusammen
    preis_hinweise = []
    rabatt_hinweise = []
    if zahl_ocr_risiko(artikel.get("einzelpreis", "")):
        preis_hinweise.append("Preis enthält OCR-riskante Ziffer: 8")
    for rabatt_zeile in artikel.get("rabatt_rohtexte", []):
        if zahl_ocr_risiko(rabatt_zeile):
            rabatt_hinweise.append("Rabattzeile enthält OCR-riskante Ziffer: 8")
    if artikel.get("rabatt_pruefen"):
        rabatt_hinweise.append("Rabattzeile per OCR erkannt und muss geprüft werden.")
    if artikel.get("einzelpreis", 0) > 20:
        preis_hinweise.append("Einzelpreis wirkt ungewöhnlich hoch.")
    if artikel.get("rabatt", 0) > artikel.get("einzelpreis", 0):
        rabatt_hinweise.append("Rabatt ist höher als Artikelpreis.")
    artikel["ocr_preis_hinweise"] = preis_hinweise
    artikel["ocr_rabatt_hinweise"] = rabatt_hinweise
    artikel["ocr_pruefen"] = len(artikel["ocr_preis_hinweise"]) > 0 or len(artikel["ocr_rabatt_hinweise"]) > 0
    return artikel


def ocr_preise_pruefen_und_bearbeiten(artikel_liste):
    for artikel in artikel_liste:
        if not artikel.get("ocr_preis_hinweise"):
            continue
        einzelpreis_roh = artikel["einzelpreis"]
        while True:
            eingabe = input(
                f"Artikel: {artikel['produkt']} | "
                f"ausgelesener Preis: {einzelpreis_roh:.2f} €\n"
                "Mit Enter Preis bestätigen oder neuen Preis eingeben z.B. 1,29: ").strip()
            if eingabe == "":
                break
            try:
                einzelpreis_bestaetigt = round(float(eingabe.replace(",", ".")), 2)
                if einzelpreis_bestaetigt <= 0:
                    print("Preis darf nicht 0 oder negativ sein.")
                    continue
                artikel["einzelpreis"] = einzelpreis_bestaetigt
                break
            except ValueError:
                print("Bitte einen gültigen Preis eingeben.")
    return artikel_liste


def ocr_rabatte_pruefen_und_bearbeiten(artikel_liste):
    for artikel in artikel_liste:
        if not artikel.get("ocr_rabatt_hinweise"):
            continue
        rabatt_summe = 0
        einzelpreis = artikel['einzelpreis']
        for rabatt_eintrag in artikel["rabatte"]:
            rabatt_roh = rabatt_eintrag['rohtext']
            rabatt_teile = rabatt_roh.split()
            rabatt_name = " ".join(rabatt_teile[:-1])
            
            try:
                rabatt_wert = abs(float(rabatt_teile[-1].replace(',', '.')))
            except ValueError:
                    print(f"Rabatt konnte nicht gelesen werden: {rabatt_roh}")
                    continue
            while True:
                eingabe = input(
                    f"Artikel: {artikel['produkt']} | "
                    f"ausgelesener Rabatt: {rabatt_name}: {rabatt_wert:.2f} €\n"
                    "Mit Enter Rabatt bestätigen oder korrekten Rabatt eingeben z.B. 0,29: ").strip()
                try:
                    if eingabe == "":
                        rabatt_bestaetigt = rabatt_wert
                    else:
                        rabatt_bestaetigt = round(float(eingabe.replace(',', '.')), 2)
                    if rabatt_bestaetigt < 0:
                        print("Rabatt darf nicht negativ sein.")
                        continue
                    if rabatt_summe + rabatt_bestaetigt > einzelpreis:
                        print("Gesamtrabatt ist größer als der Preis. Bitte prüfen.")
                        continue
                    rabatt_eintrag['betrag'] = rabatt_bestaetigt
                    rabatt_summe += rabatt_bestaetigt
                    break
                except ValueError:
                    print("Bitte einen gültigen Rabatt eingeben.")
            artikel["rabatt"] = round(rabatt_summe, 2)
    return artikel_liste


def lidl_parser(relevante_zeilen, mapping, inhalte):
    letzter_artikel = None
    artikel_liste = []
    for zeile in relevante_zeilen:
        zeile = zeile.strip()
        if 'kg x' in zeile:
            if letzter_artikel is not None:
                teile = zeile.split()
                try:
                    menge_roh = float(teile[0].replace(',' , '.'))
                    einheit = str(teile[1].strip())
                    letzter_artikel['menge_roh'] = menge
                    letzter_artikel['einheit'] = einheit
                    letzter_artikel['inhalt_menge_roh'] = menge
                    letzter_artikel['inhalt_einheit'] = einheit
                except (ValueError, IndexError, ZeroDivisionError):
                    pass
            continue
        if 'abatt' in zeile:
            if letzter_artikel is not None:
                letzter_artikel["rabatt_pruefen"] = True
                letzter_artikel["rabatt_rohtexte"].append(zeile)
                rabatt_typ = "Unbekannt"

                if "lidl plus" in zeile.lower():
                    rabatt_typ = "Lidl Plus"
                elif "aktionsrabatt" in zeile.lower():
                    rabatt_typ = "Aktionsrabatt"
                letzter_artikel["rabatte"].append({"typ": rabatt_typ, "rohtext": zeile, "betrag": None})
            continue
        teile = zeile.split()
        einzelpreis_roh = None
        preis_index = None
        for i in range (len(teile) -1, -1, -1):
            preis_text = teile[i].replace(',', '.')
            try:
                einzelpreis_roh = float(preis_text)
                preis_index = i
                produkt_ende = preis_index
                if preis_index >= 3 and teile[preis_index - 2].lower() in ["x", "×"]:
                    produkt_ende = preis_index - 3
                elif preis_index >= 2 and teile[preis_index - 2].lower().endswith("x"):
                    produkt_ende = preis_index - 2
                break
            except ValueError:
                continue
        if einzelpreis_roh is None:
            continue
        menge = lidl_menge_aus_artikelzeile(zeile)
        produkt_teile = teile[:produkt_ende]
        produkt = ' '.join(produkt_teile)
        if 'bio' in produkt.lower():
            bio = 'ja'
        else:
            bio = 'unbekannt'
        inhalt = produkt_inhalte_bestimmen(produkt, inhalte)
        kategorie = kategorie_vorschlagen(produkt, kategorie_zuordnung)
        
        artikel = {"produkt": produkt, 
                   "produkt_original": produkt, 
                   "produkt_standard": produkt_standard_bestimmen(produkt, mapping), 
                   "bio": bio, 
                   "kategorie": kategorie, 
                   "menge": menge, 
                   "einheit": 'Packung', 
                   "einzelpreis": einzelpreis_roh, 
                   "rabatt": 0,
                   "rabatte": [],
                   "rabatt_rohtexte": [],
                   "rabatt_pruefen": False,
                   "inhalt_menge": inhalt['inhalt_menge'],
                   "inhalt_einheit": inhalt['inhalt_einheit'], 
                   "haendler": 'Lidl', 
                   "datum": None, 
                   "kalenderwoche": None, 
                   "monat": None, 
                   "vollstaendig": False}
        artikel_liste.append(artikel)
        letzter_artikel = artikel
    return artikel_liste, mapping, inhalte


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


def rewe_pdf_import(dateiname, mapping, inhalte):
    text = pdf_text_auslesen(dateiname)
    artikel_liste, mapping, inhalte = rewe_artikel_aus_text(text, mapping, inhalte)
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
    return artikel_liste, mapping, inhalte


def vollstaendigkeit_pruefen(artikel):
    relevante_felder = ["produkt", "produkt_standard", "bio", "kategorie", "menge", "einheit", "inhalt_menge", "inhalt_einheit", "einzelpreis", "haendler", "datum"]
    fehlende_felder = []
    for feld in relevante_felder:
        if artikel.get(feld) in [None, "", "unbekannt"]:
            fehlende_felder.append(feld)
    artikel["fehlende_felder"] = fehlende_felder
    artikel["vollstaendig"] = len(fehlende_felder) == 0
    return artikel


def unvollstaendige_artikel_sammeln(einkaeufe):
    unvollstaendige = []
    for artikel in einkaeufe:
        vollstaendigkeit_pruefen(artikel)
        if not artikel.get('vollstaendig', False):
            unvollstaendige.append(artikel)
    return unvollstaendige


def artikel_mit_fehlendem_feld_finden(einkaeufe, feldname):
    treffer = []
    for artikel in einkaeufe:
        vollstaendigkeit_pruefen(artikel)
        if feldname in artikel.get('fehlende_felder', []):
            treffer.append(artikel)
    return treffer


def feld_mehrfach_setzen(artikel_liste, feldname, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung):
    while True:
        for i, artikel in enumerate(artikel_liste, start=1):
            print(f"{i} = {artikel['datum']} | "
                  f"{artikel['produkt']} | "
                  f"aktuell: {artikel.get(feldname)}")    
        print("x = zurück")
        try:
            eingabe = (input('Welche Nummern ändern? z.B. 1, 4, 8: ')).strip().lower()
            if eingabe == 'x':
                return artikel_liste, kategorie_zuordnung
            indices = []
            teile = eingabe.split(',')
            for teil in teile:    
                indices.append(int(teil.strip()))
            print(f'\n{feldname}')
            wert = wert_fuer_feld_abfragen(feldname, kategorien_liste, einheiten_liste, haendler_liste)
            if wert is None:
                return artikel_liste, kategorie_zuordnung
            for i in indices:
                if 1<= i <= len(artikel_liste):
                    artikel = artikel_liste[i-1]
                    artikel[feldname]= wert
                    if feldname == 'kategorie':
                        kategorie_zuordnung = kategorie_zuordnung_lernen(artikel['produkt'], wert, kategorie_zuordnung)
                    vollstaendigkeit_pruefen(artikel)
                else:
                    print(f'{i} ist keine gültige Nummer.')
                    continue
            return artikel_liste, kategorie_zuordnung
        except ValueError:
            print('Bitte eine Zahl eingeben oder x zum Zurückgehen.')


def wert_fuer_feld_abfragen(feldname, kategorien_liste, einheiten_liste, haendler_liste):
    if feldname == 'bio':
        while True:
            bio = eingabe_mit_abbruch('Bio')
            if bio is None:
                return None
            bio = bio.lower()
            if bio in ['ja', 'nein']:
                return bio
            else:
                print("Bitte 'ja' oder 'nein' eingeben.")
    elif feldname == 'kategorie':
        kategorie = auswahl_aus_liste( "Kategorie auswählen:", kategorien_liste, stammdaten, "KATEGORIEN", stammdaten_datei)
        if kategorie is None:
            return None
        return kategorie
    elif feldname in ['menge', 'inhalt_menge']:
        menge = zahl_eingeben('Menge')
        if menge is None:
            return None
        return menge
    elif feldname in ['einheit', 'inhalt_einheit']:
        einheit = auswahl_aus_liste( "Einheit auswählen:", einheiten_liste, stammdaten, "EINHEITEN", stammdaten_datei)
        if einheit is None:
            return None
        return einheit
    elif feldname == 'haendler':
        haendler = auswahl_aus_liste("Händler auswählen:", haendler_liste, stammdaten, "HAENDLER", stammdaten_datei)
        if haendler is None:
            return None
        return haendler


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


def import_nachbearbeitung(neue_artikel, dateien, app_daten, stammdaten_context):
    dateiname = dateien['einkaeufe']
    produkt_mapping_datei =dateien['produkt_mapping'] 
    produkt_inhalte_datei = dateien['produkt_inhalte']
    
    einkaeufe = app_daten['einkaeufe']
    mapping = app_daten['mapping']
    inhalte = app_daten['inhalte']
    produkt_stammdaten = app_daten['produkt_stammdaten']

    einheiten_liste = stammdaten_context ['einheiten_liste']

    neue_artikel, mapping = produkt_mapping_ergaenzen(neue_artikel, mapping)
    automatisch_ergaenzt = []
    for artikel in neue_artikel:
        vorher = artikel.copy()
        produkt_stammdaten_anwenden(artikel, produkt_stammdaten)
        if artikel != vorher:
            automatisch_ergaenzt.append(artikel)
    if automatisch_ergaenzt:
        print("Folgende Artikel wurden automatisch durch Produktstammdaten ergänzt:")
        for artikel in automatisch_ergaenzt:
            print(f"{artikel['produkt_original']} → "
                  f"{artikel['produkt_standard']} | "
                  f"{artikel['bio']} | "
                  f"{artikel['kategorie']} | "
                  f"{artikel['menge']} {artikel['einheit']} | "
                  f"{artikel['inhalt_menge']} {artikel['inhalt_einheit']}")
    print("Bitte jetzt die enthaltenen Menge und die Einheit dazu angeben.")
    neue_artikel, inhalte, einheiten_liste = produkt_inhalte_ergaenzen(neue_artikel, inhalte, einheiten_liste)
    for artikel in neue_artikel:
        vollstaendigkeit_pruefen(artikel)
    unvollstaendige = unvollstaendige_artikel_sammeln(neue_artikel)
    print(f'{len(unvollstaendige)} importierte Artikel sind noch unvollständig.')
    einkaeufe.extend(neue_artikel)
    daten_speichern(dateiname, einkaeufe)
    produkt_mapping_speichern(produkt_mapping_datei, mapping)
    produkt_inhalte_speichern(produkt_inhalte_datei, inhalte)
    return app_daten, stammdaten_context


def eintrag_hinzufuegen(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung, mapping, inhalte):
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
    inhalt_menge = zahl_eingeben('Menge in der Verpackung')
    if inhalt_menge is None:
        return einkaeufe, kategorie_zuordnung
    inhalt_einheit = auswahl_aus_liste( "Einheit der Verpackungsmenge auswählen:", einheiten_liste, stammdaten, "EINHEITEN", stammdaten_datei)
    if inhalt_einheit is None:
        return einkaeufe, kategorie_zuordnung
    haendler = auswahl_aus_liste("Händler auswählen:", haendler_liste, stammdaten, "HAENDLER", stammdaten_datei)
    if haendler is None:
        return einkaeufe, kategorie_zuordnung
    datum_iso, kw, monat = datum_eingeben('Datum')
    if datum_iso is None:
        return einkaeufe, kategorie_zuordnung
    inhalt = produkt_inhalte_bestimmen(produkt, inhalte)
    vollstaendig = True
    
    artikel = {"produkt": produkt, "produkt_original": produkt, "produkt_standard": produkt_standard_bestimmen(produkt, mapping), "bio": bio, "kategorie": kategorie, "menge": menge, "einheit": einheit, "einzelpreis": preis_pro_einheit, "inhalt_menge": inhalt['inhalt_menge'],
"inhalt_einheit": inhalt['inhalt_einheit'], "haendler": haendler, "datum": datum_iso, "kalenderwoche": kw, "monat": monat, 'vollstaendig': vollstaendig}
    vollstaendigkeit_pruefen(artikel)

    einkaeufe.append(artikel)
    return einkaeufe, kategorie_zuordnung, mapping, inhalte


def schnellerfassung(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung, mapping, inhalte):
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
    inhalt = produkt_inhalte_bestimmen(produkt, inhalte)
    vollstaendig = False
    
    artikel = {"produkt": produkt, "produkt_original": produkt, "produkt_standard": produkt_standard_bestimmen(produkt, mapping), "bio": bio, "kategorie": kategorie, "menge": menge, "einheit": einheit, "einzelpreis": preis_pro_einheit, "inhalt_menge": inhalt['inhalt_menge'],
"inhalt_einheit": inhalt['inhalt_einheit'], "haendler": haendler, "datum": datum_iso, "kalenderwoche": kw, "monat": monat, 'vollstaendig': vollstaendig}
    
    einkaeufe.append(artikel)
    return einkaeufe, kategorie_zuordnung, mapping, inhalte


def eintrag_vervollstaendigen(app_daten, stammdaten_context):
    einkaeufe = app_daten['einkaeufe']
    mapping = app_daten['mapping']
    inhalte = app_daten['inhalte']
    kategorie_zuordnung = app_daten['kategorie_zuordnung']
    produkt_stammdaten = app_daten['produkt_stammdaten']

    einheiten_liste = stammdaten_context ['einheiten_liste']
    kategorien_liste = stammdaten_context['kategorien_liste']
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return app_daten
    eintraege_unvollstaendig = unvollstaendige_artikel_sammeln(einkaeufe)
    if not eintraege_unvollstaendig:
        print("Keine unvollständigen Einträge vorhanden.")
        return app_daten
    for i, artikel in enumerate(eintraege_unvollstaendig, start=1):
        print(f"{i}:{artikel['datum']} | {artikel['produkt']} | {', '.join(artikel['fehlende_felder'])}")
        print("-" * 100)
    while True:
        try:
            auswahl = eingabe_mit_abbruch('Nummer des Eintrags: ')
            if auswahl is None:
                return app_daten
            auswahl = int(auswahl)
            if 1 <= auswahl <= len(eintraege_unvollstaendig):
                index = auswahl - 1
                eintrag_auswahl = eintraege_unvollstaendig[index]
                if 'produkt_original' not in eintrag_auswahl:
                    eintrag_auswahl['produkt_original'] = eintrag_auswahl['produkt']
                if 'produkt_standard' not in eintrag_auswahl:
                    eintrag_auswahl['produkt_standard'] = produkt_standard_bestimmen(eintrag_auswahl['produkt'], mapping)
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
                if eintrag_auswahl['inhalt_menge'] == None:
                    inhalt_menge = zahl_eingeben('Menge in der Verpackung')
                    if inhalt_menge is None:
                        continue
                    eintrag_auswahl['inhalt_menge'] = inhalt_menge
                if eintrag_auswahl['inhalt_einheit'] == 'unbekannt':
                    inhalt_einheit = auswahl_aus_liste( "Verpackungseinheit auswählen:", einheiten_liste, stammdaten, "EINHEITEN", stammdaten_datei)
                    if inhalt_einheit is None:
                        continue
                    eintrag_auswahl['inhalt_einheit'] = inhalt_einheit
                inhalte[eintrag_auswahl['produkt_original']] = {'inhalt_menge': eintrag_auswahl['inhalt_menge'], 'inhalt_einheit': eintrag_auswahl['inhalt_einheit']}
                vollstaendigkeit_pruefen(eintrag_auswahl)
                if eintrag_auswahl['vollstaendig']:
                    produkt_stammdaten = produkt_stammdaten_lernen(eintrag_auswahl, produkt_stammdaten)
                return app_daten
            else:
                print(f"Bitte Zahl zwischen 1 und {len(eintraege_unvollstaendig)} eingeben.")
        except ValueError:
            print("Bitte eine Zahl eingeben.")
    

def eintrag_bearbeiten(app_daten, stammdaten_context):
    einkaeufe = app_daten['einkaeufe']
    mapping = app_daten['mapping']
    inhalte = app_daten['inhalte']
    kategorie_zuordnung = app_daten['kategorie_zuordnung']

    einheiten_liste = stammdaten_context ['einheiten_liste']
    kategorien_liste = stammdaten_context['kategorien_liste']
    haendler_liste = stammdaten_context['haendler_liste']
    
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return app_daten
    eintraege_vollstaendig = []
    for artikel in einkaeufe:
        if not isinstance(artikel, dict):
            continue
        if artikel["vollstaendig"]:
            eintraege_vollstaendig.append(artikel)
    if not eintraege_vollstaendig:
        print("Keine vollständigen Einträge vorhanden.")
        return app_daten
    for i, artikel in enumerate(eintraege_vollstaendig, start=1):
        print(f"{i}: {artikel['datum']} | {artikel['produkt']} | {artikel['bio']} | {artikel['kategorie']} | {artikel['menge']} {artikel['einheit']} | {artikel['einzelpreis']:.2f} € | {artikel['inhalt_menge']} {artikel['inhalt_einheit']} | {artikel['haendler']}")
        print("-" * 100)
    while True:
        try:
            auswahl = eingabe_mit_abbruch('Nummer des Eintrags: ')
            if auswahl is None:
                return app_daten
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
                    print('7 = Verpackungsmenge ändern')
                    print('8 = Verpackungseinheit ändern')
                    print('9 = Händler ändern')
                    print('10 = Kaufdatum ändern')
                    print('99 = Bearbeitung beenden')

                    wahl = input('Auswahl: ').strip()
                    if wahl == '1':
                        print(f"Aktueller Wert: {eintrag_auswahl['produkt']}")
                        produkt = eingabe_mit_abbruch('Produkt')
                        if produkt is None:
                            continue
                        produkt = produkt.title()
                        while True:
                            wert = input(f'Soll {produkt} auch der Standardname sein? ja/nein: ').strip().lower()
                            if wert == 'ja':
                                eintrag_auswahl['produkt_standard'] = produkt
                                mapping[eintrag_auswahl['produkt_original']] = produkt
                                break
                            elif wert == 'nein':
                                break
                            else:
                                print("Bitte ja oder nein eingeben.")
                        eintrag_auswahl['produkt'] = produkt
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '2':
                        while True:
                            print(f"Aktueller Wert: {eintrag_auswahl['bio']}")
                            bio = eingabe_mit_abbruch('Bio')
                            if bio is None:
                                break
                            bio = bio.lower()
                            if bio in ['ja', 'nein']:
                                eintrag_auswahl['bio'] = bio
                                break
                            else:
                                print("Bitte 'ja' oder 'nein' eingeben.")
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '3':
                        print(f"Aktueller Wert: {eintrag_auswahl['kategorie']}")
                        kategorie = auswahl_aus_liste( "Kategorie auswählen:", kategorien_liste, stammdaten, "KATEGORIEN", stammdaten_datei)
                        if kategorie is None:
                            continue
                        eintrag_auswahl['kategorie'] = kategorie
                        kategorie_zuordnung = kategorie_zuordnung_lernen(eintrag_auswahl['produkt'], eintrag_auswahl['kategorie'], kategorie_zuordnung)
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '4':
                        print(f"Aktueller Wert: {eintrag_auswahl['menge']}")
                        menge = zahl_eingeben('Menge')
                        if menge is None:
                            continue
                        eintrag_auswahl['menge'] = menge
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '5':
                        print(f"Aktueller Wert: {eintrag_auswahl['einheit']}")
                        einheit = auswahl_aus_liste( "Einheit auswählen:", einheiten_liste, stammdaten, "EINHEITEN", stammdaten_datei)
                        if einheit is None:
                            continue
                        eintrag_auswahl['einheit'] = einheit
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '6':
                        print(f"Aktueller Wert: {eintrag_auswahl['einzelpreis']}")
                        einzelpreis = zahl_eingeben('Einzelpreis')
                        if einzelpreis is None:
                            continue
                        eintrag_auswahl['einzelpreis'] = einzelpreis
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '7':
                        print(f"Aktueller Wert: {eintrag_auswahl['inhalt_menge']}")
                        inhalt_menge = zahl_eingeben('Menge')
                        if inhalt_menge is None:
                            continue
                        eintrag_auswahl['inhalt_menge'] = inhalt_menge
                        inhalte[eintrag_auswahl['produkt_original']] = {"inhalt_menge": eintrag_auswahl['inhalt_menge'],"inhalt_einheit": eintrag_auswahl['inhalt_einheit']}
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '8':
                        print(f"Aktueller Wert: {eintrag_auswahl['inhalt_einheit']}")
                        inhalt_einheit = auswahl_aus_liste( "Einheit auswählen:", einheiten_liste, stammdaten, "EINHEITEN", stammdaten_datei)
                        if inhalt_einheit is None:
                            continue
                        eintrag_auswahl['inhalt_einheit'] = inhalt_einheit
                        inhalte[eintrag_auswahl['produkt_original']] = {"inhalt_menge": eintrag_auswahl['inhalt_menge'],"inhalt_einheit": eintrag_auswahl['inhalt_einheit']}
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '9':
                        print(f"Aktueller Wert: {eintrag_auswahl['haendler']}")
                        haendler = auswahl_aus_liste("Händler auswählen:", haendler_liste, stammdaten, "HAENDLER", stammdaten_datei)
                        if haendler is None:
                            continue
                        eintrag_auswahl['haendler'] = haendler
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '10':
                        print(f"Aktueller Wert: {eintrag_auswahl['datum']}")
                        datum_iso, kw, monat = datum_eingeben('Datum')
                        if datum_iso is None:
                            continue
                        eintrag_auswahl['kalenderwoche'] = kw
                        eintrag_auswahl['monat'] = monat
                        eintrag_auswahl['datum'] = datum_iso
                        vollstaendigkeit_pruefen(eintrag_auswahl)
                    elif wahl == '99':
                        app_daten['einkaeufe'] = einkaeufe
                        app_daten['mapping'] = mapping
                        app_daten['inhalte'] = inhalte
                        app_daten['kategorie_zuordnung'] = kategorie_zuordnung
                        return app_daten
                    else:
                        print('Bitte Zahl zwischen 1 und 9 eingeben.')
        except ValueError:
            print("Bitte eine Zahl eingeben.")


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


def produkt_uebersicht(produkt_stammdaten):
    if not produkt_stammdaten:
        print('Keine Produkt-Stammdaten vorhanden.')
        return
    for produkt_original, daten in sorted(produkt_stammdaten.items(), key=lambda eintrag: eintrag[1]['produkt_standard']):
        print(f" {daten['produkt_standard']} | {daten['bio']} | {daten['kategorie']} | {daten['einheit']} | {daten['inhalt_menge']} {daten['inhalt_einheit']} ")
        print("-" * 80)


def alle_einkaeufe_anzeigen(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
##        print('Es wurden folgende Artikel gekauft:\n')
    print('Alle vollständigen Einträge\n')
    for artikel in sorted(einkaeufe, key=lambda x: x['datum']):
        if artikel['vollstaendig']:
            vergleichspreis, vergleichsmenge = vergleichspreis_berechnen(artikel)
            if vergleichspreis is None:
                vergleichspreis_text = "unbekannt"
            else:
                vergleichspreis_text = f"{vergleichspreis:.2f} €/{vergleichsmenge}"
            print(f"{artikel['datum']} | {artikel['produkt']} | {artikel['produkt_standard']} | {artikel['bio']} | {artikel['kategorie']} | {artikel['menge']} {artikel['einheit']} | {artikel['einzelpreis']:.2f} € | Vergleichspreis: {vergleichspreis_text} | {artikel['inhalt_menge']} {artikel['inhalt_einheit']} | {artikel['haendler']}")
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
    unvollstaendige = unvollstaendige_artikel_sammeln(einkaeufe)
    if len(unvollstaendige) == 0:
        print("Alle Einträge sind vollständig und können ausgewertet werden.")
        return
    print("Folgende Einträge sind unvollständig und müssen bearbeitet werden:\n")
    for artikel in unvollstaendige:
        print(f"{artikel['datum']} | {artikel['produkt']} | {', '.join(artikel['fehlende_felder'])}")
        print("-" * 100)
                                

def einkaufsstatistik(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    bon_daten = {}
    artikel_anzahl = 0
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            bon_id = artikel['bon_id']
            kosten = artikel['einzelpreis']
            artikel_anzahl = 0 
            if bon_id in bon_daten:
                bon_daten[bon_id]['kosten'] += kosten
                bon_daten[bon_id]['artikel_anzahl'] += 1
            else:
                bon_daten[bon_id] = {'kosten':kosten, 'artikel_anzahl': 1}
                
    gesamt = sum(daten["kosten"] for daten in bon_daten.values())
    gesamt_artikel = sum(daten["artikel_anzahl"] for daten in bon_daten.values())
    anzahl_einkaeufe = len(bon_daten)
    print(f"Anzahl Einkäufe: {anzahl_einkaeufe}")
    print("-" * 30)
    print(f"Gesamtausgaben: {gesamt:.2f}")
    print("-" * 30)
    print(f"Durchschnittlicher Einkaufswert: {gesamt/anzahl_einkaeufe:.2f}")
    print("-" * 30)
    print(f"Durchschnittlicher Artikel-Anzahl: {gesamt_artikel/anzahl_einkaeufe:.2f}")
    print("-" * 30)
    for bon_id, daten in sorted(bon_daten.items()):
        anteil = daten['kosten']/gesamt*100
        print(f"{bon_id} | {daten['artikel_anzahl']} | {daten['kosten']:.2f} € | {anteil:.2f} %")
        print("-" * 50)


def produkt_historie_anzeigen(einkaeufe):
    historie_liste = []
    eingabe = eingabe_mit_abbruch('Produkt für Historie eingeben: ')
    if eingabe is None:
        return None
    for artikel in einkaeufe:
        if eingabe.strip().lower() in artikel['produkt_standard'].lower(): 
            #print(artikel['produkt_standard'])
            historie_liste.append(artikel)
    historie_liste.sort(key=lambda artikel: artikel['datum'])
    if not historie_liste:
        print('Keine passenden Artikel gefunden.')
        return None
    
    print(f"\n Produkthistorie für {eingabe}\n"
          f"Datum | Händler | Standardname | Zahlpreis | Stückpreis | Vergleichspreis\n")

    for artikel in historie_liste:
        zahlpreis = zahlpreis_berechnen(artikel)
        stueckpreis = stueckpreis_berechnen(artikel)
        vergleichspreis, vergleichsmenge = vergleichspreis_berechnen(artikel)


        print(
            f"{artikel['datum']} | "
            f"{artikel['haendler']} | "
            f"{artikel['produkt_standard']} | "
            f"{zahlpreis:.2f} € | "
            f"{stueckpreis:.2f} € | "
            f"{vergleichspreis:.2f} €/{vergleichsmenge}")

    return historie_liste


def zahlpreis_berechnen(artikel):
    preis = artikel.get('einzelpreis', 0)
    rabatt = artikel.get('rabatt', 0)
    return round(preis - rabatt, 2)


def stueckpreis_berechnen(artikel):
    menge = artikel.get('menge', 1)
    if menge in [None, 0]:
        return None
    return round(zahlpreis_berechnen(artikel) / menge, 2)


def vergleichspreis_berechnen(artikel):
    preis = zahlpreis_berechnen(artikel)
    menge = artikel['inhalt_menge']
    einheit = artikel['inhalt_einheit']
    vergleichspreis = 0
    vergleichsmenge = 'unbekannt'

    if einheit == 'g':
        vergleichspreis = float(preis/menge*1000)
        vergleichsmenge = 'kg'
        return vergleichspreis, vergleichsmenge
    elif einheit == 'ml':
        vergleichspreis = float(preis/menge*1000)
        vergleichsmenge = 'l'
        return vergleichspreis, vergleichsmenge
    elif einheit == 'kg':
        vergleichspreis = float(preis/menge)
        vergleichsmenge = einheit
        return vergleichspreis, vergleichsmenge
    elif einheit == 'l':
        vergleichspreis = float(preis/menge)
        vergleichsmenge = einheit
        return vergleichspreis, vergleichsmenge
    elif einheit == 'Stück':
        vergleichspreis = float(preis/menge)
        vergleichsmenge = einheit
        return vergleichspreis, vergleichsmenge
    elif einheit == 'Flasche':
        vergleichspreis = float(preis/menge)
        vergleichsmenge = einheit
        return vergleichspreis, vergleichsmenge
    else:
        print("Verpackungseinheit nicht hinterlegt, Vergleichspreis kann nicht berechnet werden.")
        return None, None


def kosten_nach_feld_sammeln(einkaeufe, feldname):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    daten = {}
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            gruppe = artikel[feldname]
            kosten = zahlpreis_berechnen(artikel)
            if gruppe in daten:
                daten[gruppe] += kosten
            else:
                daten[gruppe] = kosten
    return daten

def gruppen_uebersicht(einkaeufe, feldname, titel):
    daten = kosten_nach_feld_sammeln(einkaeufe, feldname)
    gesamt = sum(daten.values())
    for gruppe, kosten in sorted(daten.items(), key=lambda eintrag: eintrag[1], reverse=True):
        anteil = kosten/gesamt*100
        print(f"{gruppe} | {kosten:.2f} € | {anteil:.2f} %")
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


def menue_erfassung(dateien, app_daten, stammdaten_context):
    dateiname = dateien['einkaeufe']
    produkt_mapping_datei =dateien['produkt_mapping'] 
    produkt_inhalte_datei = dateien['produkt_inhalte']
    
    einkaeufe = app_daten['einkaeufe']
    mapping = app_daten['mapping']
    inhalte = app_daten['inhalte']
    produkt_stammdaten = app_daten['produkt_stammdaten']
    kategorie_zuordnung = app_daten['kategorie_zuordnung']

    einheiten_liste = stammdaten_context ['einheiten_liste']
    kategorien_liste = stammdaten_context['kategorien_liste']
    haendler_liste = stammdaten_context['haendler_liste']

    while True:
        print('\n' + '=' * 50)
        print('Einträge erfassen')
        print('=' * 50)
        print('1 = vollständigen Eintrag hinzufügen')
        print('2 = schnellen Eintrag hinzufügen')
        print('3 = Rewe Kassenbon importieren')
        print('4 = Lidl Kassenbon importieren')
        print('9 = zurück zum Hauptmenü')
        
        wahl = input('Menü-Auswahl: ').strip()
        
        if wahl == '1':
            einkaeufe, kategorie_zuordnung, mapping, inhalte = eintrag_hinzufuegen(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung, mapping, inhalte)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            daten_speichern(dateiname, einkaeufe)
            produkt_mapping_speichern(produkt_mapping_datei, mapping)
            produkt_inhalte_speichern(produkt_inhalte_datei, inhalte)
        elif wahl == '2':
            einkaeufe, kategorie_zuordnung, mapping, inhalte = schnellerfassung(einkaeufe, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung, mapping, inhalte)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            daten_speichern(dateiname, einkaeufe)
            produkt_mapping_speichern(produkt_mapping_datei, mapping)
            produkt_inhalte_speichern(produkt_inhalte_datei, inhalte)
        elif wahl == '3':
            pdf_dateiname = eingabe_mit_abbruch('PDF-Dateiname: ')
            if pdf_dateiname is None:
                continue
            neue_artikel, mapping, inhalte = rewe_pdf_import(pdf_dateiname, mapping, inhalte)
            if neue_artikel:
                neue_bon_id = neue_artikel[0].get('bon_id')
                if neue_bon_id is None:
                    print("Keine Bon-ID erkannt. Der Import kann nicht auf Duplikate geprüft werden.")
                if any(artikel.get('bon_id') == neue_bon_id for artikel in einkaeufe):
                    print("Dieser Bon wurde bereits importiert.")
                    continue
            print(f'{len(neue_artikel)} Artikel wurden importiert.')
            alle_einkaeufe_anzeigen(neue_artikel)
            neue_artikel, mapping = produkt_mapping_ergaenzen(neue_artikel, mapping)
            automatisch_ergaenzt = []
            for artikel in neue_artikel:
                vorher = artikel.copy()
                produkt_stammdaten_anwenden(artikel, produkt_stammdaten)
                if artikel != vorher:
                    automatisch_ergaenzt.append(artikel)
            if automatisch_ergaenzt:
                print("Folgende Artikel wurden automatisch durch Produktstammdaten ergänzt:")
                for artikel in automatisch_ergaenzt:
                    print(
                        f"{artikel['produkt_original']} → "
                        f"{artikel['produkt_standard']} | "
                        f"{artikel['bio']} | "
                        f"{artikel['kategorie']} | "
                        f"{artikel['menge']} {artikel['einheit']} | "
                        f"{artikel['inhalt_menge']} {artikel['inhalt_einheit']}")
            print("Bitte jetzt die enthaltenen Menge und die Einheit dazu angeben.")
            neue_artikel, inhalte, einheiten_liste = produkt_inhalte_ergaenzen(neue_artikel, inhalte, einheiten_liste)
            for artikel in neue_artikel:
                vollstaendigkeit_pruefen(artikel)
            text, app_daten, stammdaten_context = import_nachbearbeitung(neue_artikel, dateien, app_daten, stammdaten_context)
        elif wahl == '4':
            png_dateiname = eingabe_mit_abbruch('PNG-Dateiname: ')
            if png_dateiname is None:
                continue
            text, neue_bon_id, neue_artikel, mapping, inhalte = lidl_png_import(png_dateiname, mapping, inhalte)
#            if neue_artikel:
#                neue_bon_id = neue_artikel[0].get('bon_id')
#                if neue_bon_id is None:
#                    print("Keine Bon-ID erkannt. Der Import kann nicht auf Duplikate geprüft werden.")
#                if any(artikel.get('bon_id') == neue_bon_id for artikel in einkaeufe):
#                    print("Dieser Bon wurde bereits importiert.")
#                    continue
            print(f'{len(neue_artikel)} Artikel wurden importiert.')
            alle_einkaeufe_anzeigen(neue_artikel)
            print("\n--- Bonvergleich nach Import ---")
            lidl_bonvergleich_ausgeben(neue_artikel, text)
            unvollstaendige = unvollstaendige_artikel_sammeln(neue_artikel)
            print(f'{len(unvollstaendige)} importierte Artikel sind noch unvollständig.')
            for artikel in neue_artikel:
                ocr_pruefung_artikel(artikel)
            ocr_preise_pruefen_und_bearbeiten(neue_artikel)
            ocr_rabatte_pruefen_und_bearbeiten(neue_artikel)
            for artikel in neue_artikel:
                ocr_pruefung_artikel(artikel)
                vollstaendigkeit_pruefen(artikel)
            app_daten, stammdaten_context = import_nachbearbeitung(neue_artikel, dateien, app_daten, stammdaten_context)
            print("\n--- Bonvergleich nach Nachbearbeitung ---")
            lidl_bonvergleich_ausgeben(neue_artikel, text)

        elif wahl == '9':
            app_daten['einkaeufe'] = einkaeufe
            app_daten['mapping'] = mapping
            app_daten['inhalte'] = inhalte
            app_daten['produkt_stammdaten'] = produkt_stammdaten
            app_daten['kategorie_zuordnung'] = kategorie_zuordnung

            stammdaten_context ['einheiten_liste'] = einheiten_liste
            stammdaten_context['kategorien_liste'] = kategorien_liste
            stammdaten_context['haendler_liste'] = haendler_liste

            return app_daten
        else:
            print('Fehlerhafte Eingabe.')
            
            
def menue_bearbeiten(app_daten, stammdaten_context):
    einkaeufe = app_daten['einkaeufe']
    mapping = app_daten['mapping']
    inhalte = app_daten['inhalte']
    produkt_stammdaten = app_daten['produkt_stammdaten']
    kategorie_zuordnung = app_daten['kategorie_zuordnung']

    einheiten_liste = stammdaten_context ['einheiten_liste']
    kategorien_liste = stammdaten_context['kategorien_liste']
    haendler_liste = stammdaten_context['haendler_liste']
    
    while True:
        print('\n' + '=' * 50)
        print('Einträge bearbeiten')
        print('=' * 50)
        print('1 = Eintrag bearbeiten')
        print('2 = unvollständigen Eintrag vervollständigen')
        print('3 = Feld mehrfach setzen')
        print('4 = Produkt-Stammdaten lernen')
        print('5 = Eintrag löschen')
        print('9 = zurück zum Hauptmenü')
        
        wahl = input('Menü-Auswahl: ').strip()
        if wahl == '1':
            app_daten = eintrag_bearbeiten(app_daten, stammdaten_context)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            produkt_mapping_speichern(dateien ['produkt_mapping'], app_daten ['mapping'])
            produkt_inhalte_speichern(dateien ['produkt_inhalte'], app_daten ['inhalte'])
            daten_speichern(dateien["einkaeufe"], app_daten["einkaeufe"])
        elif wahl == '2':
            app_daten = eintrag_vervollstaendigen(app_daten, stammdaten_context)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            produkt_mapping_speichern(dateien ['produkt_mapping'], app_daten ['mapping'])
            produkt_inhalte_speichern(dateien ['produkt_inhalte'], app_daten ['inhalte'])
            daten_speichern(dateien["einkaeufe"], app_daten["einkaeufe"])
        elif wahl == '3':
            unvollstaendige_einkaeufe_anzeigen(einkaeufe)
            feldname = eingabe_mit_abbruch ("Welches Feld bearbeiten?")
            if feldname is None:
                continue
            artikel_liste = artikel_mit_fehlendem_feld_finden (einkaeufe, feldname)
            if not artikel_liste:
                print("Keine passenden Artikel gefunden.")
                continue
            artikel_liste, kategorie_zuordnung = feld_mehrfach_setzen(artikel_liste, feldname, kategorien_liste, einheiten_liste, haendler_liste, kategorie_zuordnung)
            stammdaten_aktualisieren(stammdaten, kategorie_zuordnung, stammdaten_datei)
            produkt_mapping_speichern(dateien ['produkt_mapping'], app_daten ['mapping'])
            produkt_inhalte_speichern(dateien ['produkt_inhalte'], app_daten ['inhalte'])
            daten_speichern(dateien["einkaeufe"], app_daten["einkaeufe"])
        elif wahl == '4':
            produkt_stammdaten = produkt_stammdaten_aus_vollstaendigen_artikeln_lernen(einkaeufe, produkt_stammdaten)
            produkt_stammdaten_speichern(dateien['produkt_stammdaten'], app_daten['produkt_stammdaten'])
        elif wahl == '5':
            einkaeufe = eintrag_loeschen(einkaeufe)
            daten_speichern(dateien["einkaeufe"], app_daten["einkaeufe"])
        elif wahl == '9':
            app_daten['einkaeufe'] = einkaeufe
            app_daten['mapping'] = mapping
            app_daten['inhalte'] = inhalte
            app_daten['produkt_stammdaten'] = produkt_stammdaten
            app_daten['kategorie_zuordnung'] = kategorie_zuordnung

            stammdaten_context ['einheiten_liste'] = einheiten_liste
            stammdaten_context['kategorien_liste'] = kategorien_liste
            stammdaten_context['haendler_liste'] = haendler_liste

            return app_daten
        else:
            print('Fehlerhafte Eingabe.')
    
        
def menue_auswertungen(app_daten):
    einkaeufe = app_daten['einkaeufe']
    produkt_stammdaten = app_daten['produkt_stammdaten']

    auswahl = {
        '5': ('kategorie', 'Kategorieübersicht'),
        '6': ('haendler', 'Händlerübersicht'),
        '7': ('monat', 'Monatsübersicht'),
        '8': ('kalenderwoche', 'Wochenübersicht')}

    while True:
        print('\n' + '=' * 50)
        print('Auswertungen')
        print('=' * 50)
        print('1 = alle Einkäufe anzeigen')
        print('2 = unvollständige Einträge anzeigen')
        print('3 = Einkaufsstatistik')
        print('4 = Produktübersicht')
        print('5 = Kategorieübersicht')
        print('6 = Händlerübersicht')
        print('7 = Monatsübersicht')
        print('8 = Wochenübersicht')
        print('9 = zurück zum Hauptmenü')

        wahl = input('Menü-Auswahl: ').strip()
        print(f"DEBUG wahl: {repr(wahl)}")
        print(f"DEBUG wahl in auswahl: {wahl in auswahl}")
 
        if wahl == '1':
            alle_einkaeufe_anzeigen(einkaeufe)
        elif wahl == '2':
            unvollstaendige_einkaeufe_anzeigen(einkaeufe)
        elif wahl == '3':
            einkaufsstatistik(einkaeufe)
        elif wahl == '4':
            produkt_uebersicht(produkt_stammdaten)
        elif wahl in auswahl:
            feldname, titel = auswahl[wahl]
            print(f" Es werden {feldname} und {titel} übergeben.")
            gruppen_uebersicht(einkaeufe, feldname, titel)
        elif wahl == '9':
            app_daten['einkaeufe'] = einkaeufe
            app_daten['produkt_stammdaten'] = produkt_stammdaten
            return app_daten
        else:
            print('Fehlerhafte Eingabe.')
    

# ------------------------
# Hauptprogramm (Menü)
# ------------------------

if __name__ == "__main__":
    BASIS_ORDNER = Path(__file__).parent

    dateiname = BASIS_ORDNER / "einkaeufe.json"
    stammdaten_datei = BASIS_ORDNER / "stammdaten.json"
    produkt_mapping_datei = BASIS_ORDNER / "produkt_mapping.json"
    produkt_inhalte_datei = BASIS_ORDNER / "produkt_inhalte.json"
    produkt_stammdaten_datei = BASIS_ORDNER / "produkt_stammdaten.json"

    stammdaten = stammdaten_laden(stammdaten_datei)
    mapping = produkt_mapping_laden(produkt_mapping_datei)
    inhalte = produkt_inhalte_laden(produkt_inhalte_datei)
    produkt_stammdaten = produkt_stammdaten_laden(produkt_stammdaten_datei)

    kategorien_liste = stammdaten.get("KATEGORIEN", [])
    haendler_liste = stammdaten.get("HAENDLER", [])
    einheiten_liste = stammdaten.get("EINHEITEN", [])
    kategorie_zuordnung = stammdaten.get("KATEGORIE_ZUORDNUNG", {})
    if not isinstance(kategorie_zuordnung, dict):
        kategorie_zuordnung = {}
    einkaeufe = daten_laden(dateiname)

    dateien = {
    "einkaeufe": dateiname,
    "stammdaten": stammdaten_datei,
    "produkt_mapping": produkt_mapping_datei,
    "produkt_inhalte": produkt_inhalte_datei,
    "produkt_stammdaten": produkt_stammdaten_datei
    }
    app_daten = {
    "einkaeufe": einkaeufe,
    "mapping": mapping,
    "inhalte": inhalte,
    "produkt_stammdaten": produkt_stammdaten,
    "kategorie_zuordnung": kategorie_zuordnung
    }
    stammdaten_context = {
    "stammdaten": stammdaten,
    "kategorien_liste": kategorien_liste,
    "einheiten_liste": einheiten_liste,
    "haendler_liste": haendler_liste}

    while True:
        print('\n' + '=' * 50)
        print('Einkaufsprotokoll')
        print('=' * 50)
        print('1 = Erfassung')
        print('2 = Bearbeitung')
        print('3 = Auswertungen')
        print('4 = Testbereich')
        print('9 = Programm beenden')

        wahl = input('Menü-Auswahl: ').strip()
    
        if wahl == '1':
            app_daten = menue_erfassung(dateien, app_daten, stammdaten_context)
        elif wahl == '2':
            app_daten = menue_bearbeiten(app_daten, stammdaten_context)
        elif wahl == '3':
            app_daten = menue_auswertungen(app_daten)
        elif wahl == '4':
            historie_liste = produkt_historie_anzeigen(einkaeufe)
        elif wahl == '9':
            daten_speichern(dateien["einkaeufe"], app_daten["einkaeufe"])
            print('Programm beendet.')
            break
        else:
            print('Fehlerhafte Eingabe.')
