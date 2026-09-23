"""Streamlit front end.  Run:  streamlit run app.py"""

import pandas as pd
import streamlit as st

from petcompare import store
from petcompare.match import group, summarise

st.set_page_config(page_title="SG Pet Food Price Compare", layout="wide")
st.title("Singapore pet food price comparison")

con = store.connect(st.sidebar.text_input("Database", "petcompare.db"))

with st.sidebar:
    st.header("Filters")
    query = st.text_input("Search", placeholder="royal canin mini adult")
    species = st.selectbox("Pet", ["", "dog", "cat", "small_animal"])
    subclass = st.selectbox("Sub-class", ["", "dry", "wet", "treats", "raw",
                                          "freeze_dried", "supplement",
                                          "prescription"])
    formulation = st.selectbox("Formulation", ["", "grain_free", "puppy", "kitten",
                                               "adult", "senior", "sensitive",
                                               "weight_care", "indoor",
                                               "sterilised", "high_protein"])
    sort = st.radio("Sort by", ["Price: high to low", "Price: low to high",
                                "$/kg: high to low", "$/kg: low to high"])
    in_stock = st.checkbox("In stock only", True)
    limit = st.slider("Max rows", 20, 1000, 200)

sort_key = {"Price: high to low": "price_desc", "Price: low to high": "price_asc",
            "$/kg: high to low": "per_kg_desc", "$/kg: low to high": "per_kg_asc"}[sort]

rows = store.search(con, query, species=species or None, subclass=subclass or None,
                    formulation=formulation or None, in_stock_only=in_stock,
                    sort=sort_key, limit=limit)

tab_list, tab_compare, tab_stock = st.tabs(["Listings", "Same product across shops",
                                            "Stockists by brand"])

with tab_list:
    if not rows:
        st.info("No results. Run `python -m petcompare.cli crawl` first.")
    else:
        df = pd.DataFrame([dict(r) for r in rows])
        show = df[["price", "price_per_kg", "total_grams", "brand", "subclass",
                   "formulation", "retailer", "title", "product_url"]]
        st.caption(f"{len(show)} listings")
        st.dataframe(
            show, use_container_width=True, hide_index=True,
            column_config={
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "price_per_kg": st.column_config.NumberColumn("$/kg", format="$%.2f"),
                "total_grams": st.column_config.NumberColumn("Pack (g)", format="%.0f"),
                "product_url": st.column_config.LinkColumn("Link", display_text="open"),
            })

with tab_compare:
    clusters = [c for c in group(rows) if len(c) >= 2]
    clusters.sort(key=lambda c: -(summarise(c)["spread"] or 0))
    if not clusters:
        st.info("Nothing in the current filter is sold by more than one shop.")
    for c in clusters[:40]:
        s = summarise(c)
        size = f"{s['grams']:.0f} g" if s["grams"] else "size unknown"
        with st.expander(
            f"{s['brand'] or '?'} — {s['label'][:70]}  ·  {size}  ·  "
            f"save ${s['spread']:.2f} ({s['spread_pct']}%)"
        ):
            d = pd.DataFrame([{"Retailer": r["retailer"], "Price": r["price"],
                               "$/kg": r["price_per_kg"], "Listing": r["title"],
                               "Link": r["product_url"]}
                              for r in sorted(c, key=lambda x: -x["price"])])
            st.dataframe(d, use_container_width=True, hide_index=True,
                         column_config={"Link": st.column_config.LinkColumn(
                             display_text="open")})

with tab_stock:
    brand = st.text_input("Brand", "Royal Canin")
    if brand:
        sk = store.stockists(con, brand)
        if sk:
            st.dataframe(pd.DataFrame([dict(r) for r in sk]),
                         use_container_width=True, hide_index=True)
        else:
            st.info("No stockists for that brand in the database yet.")
