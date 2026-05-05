# app.py
import streamlit as st
import pandas as pd

from Einkaufsanalyse import daten_laden, stammdaten_laden

dateiname = "einkaeufe.json"
stammdaten_datei = "stammdaten.json"

einkaeufe = daten_laden(dateiname)
stammdaten = stammdaten_laden(stammdaten_datei)

st.title("🛒 Einkaufsanalyse")

seite = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Artikel", "Import", "Stammdaten"]
)

if seite == "Dashboard":
    st.header("Dashboard")

    df = pd.DataFrame(einkaeufe)

    if df.empty:
        st.info("Noch keine Einkäufe vorhanden.")
    else:
        st.metric("Anzahl Artikel", len(df))
        st.metric("Gesamtausgaben", f"{df['einzelpreis'].sum():.2f} €")

        st.subheader("Ausgaben nach Kategorie")
        st.bar_chart(df.groupby("kategorie")["einzelpreis"].sum())

elif seite == "Artikel":
    st.header("Artikelübersicht")

    df = pd.DataFrame(einkaeufe)

    if df.empty:
        st.info("Keine Artikel vorhanden.")
    else:
        kategorie_filter = st.selectbox(
            "Kategorie filtern",
            ["Alle"] + sorted(df["kategorie"].dropna().unique())
        )

        if kategorie_filter != "Alle":
            df = df[df["kategorie"] == kategorie_filter]

        st.dataframe(df)

elif seite == "Import":
    st.header("Import")

    st.info("Hier könnte später der REWE-PDF-Import ausgelöst werden.")

elif seite == "Stammdaten":
    st.header("Stammdaten")

    st.write("Kategorien")
    st.write(stammdaten.get("KATEGORIEN", []))

    st.write("Händler")
    st.write(stammdaten.get("HAENDLER", []))

    st.write("Einheiten")
    st.write(stammdaten.get("EINHEITEN", []))