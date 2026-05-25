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

    def haendler_uebersicht(einkaeufe):
    daten = kosten_nach_feld_sammeln(einkaeufe, 'kategorie')
    gesamt = sum(daten.values())
    for haendler, kosten in sorted(daten.items(), key=lambda eintrag: eintrag[1], reverse=True):
        anteil = kosten/gesamt*100
        print(f"{haendler} | {kosten:.2f} €  | {anteil:.2f} %")
        print("-" * 40)


def monat_uebersicht(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    monat_daten = {}
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            monat = artikel['monat']
            kosten = artikel['einzelpreis']
            if monat in monat_daten:
                monat_daten[monat] += kosten
            else:
                monat_daten[monat] = kosten
    if not monat_daten:
        print("Keine vollständigen Einträge für die Monatsübersicht vorhanden.")
        return
    gesamt = sum(monat_daten.values())
    for monat, kosten in sorted(monat_daten.items()):
        anteil = kosten/gesamt*100
        print(f"Monat {monat} | {kosten:.2f} € | {anteil:.2f} %")
        print("-" * 40)


def woche_uebersicht(einkaeufe):
    if not einkaeufe:
        print('Keine Einkäufe vorhanden.')
        return
    woche_daten = {}
    for artikel in einkaeufe:
        if artikel['vollstaendig']:
            woche = artikel['kalenderwoche']
            kosten = artikel['einzelpreis']
            if woche in woche_daten:
                woche_daten[woche] += kosten
            else:
                woche_daten[woche] = kosten
    if not woche_daten:
        print("Keine vollständigen Einträge für die Wochenübersicht vorhanden.")
        return
    gesamt = sum(woche_daten.values())
    for woche, kosten in sorted(woche_daten.items()):
        anteil = kosten/gesamt*100
        print(f"Kalenderwoche {woche} | {kosten:.2f} € | {anteil:.2f} %")
        print("-" * 40)