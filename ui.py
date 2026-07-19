
import time
import pandas as pd
import streamlit as st

from directory_finder import get_partner_directories, get_partners


st.set_page_config(
    page_title="Directory-Scraper",
    
    layout="wide"
)



st.title("Directory-Scraper")


st.sidebar.header("Settings")

platform = st.sidebar.selectbox(
    "Platform",
    ["Zoho", "Microsoft", "Both"]
)

enrich_details = st.sidebar.checkbox(
    "Enrich Website & LinkedIn",
    value=True
)



directories_tab, partners_tab = st.tabs(
    [" Partner Directories", " Partners"]
)




with directories_tab:

    st.subheader("Partner Directories")

    if st.button("Fetch Directories", use_container_width=True):

        progress = st.progress(0)
        status = st.empty()

        status.write("Fetching directories...")

        for i in range(15):
            progress.progress((i + 1) * 5)
            time.sleep(0.03)

        directories = get_partner_directories(platform)

        progress.progress(100)
        status.success("Directories loaded!")

        if not directories:
            st.warning("No directories found.")

        else:

            directories_df = pd.DataFrame(directories)

            st.metric("Directories Found", len(directories_df))

            st.dataframe(
                directories_df,
                hide_index=True,
                use_container_width=True
            )

            st.download_button(
                "⬇ Download Directories CSV",
                directories_df.to_csv(index=False).encode("utf-8"),
                "partner_directories.csv",
                "text/csv",
                use_container_width=True
            )



with partners_tab:

    st.subheader("Partners")

    if st.button("Fetch Partners", use_container_width=True):

        progress = st.progress(0)
        status = st.empty()

        status.write("Initializing scraper...")

        for i in range(30):
            progress.progress(i + 1)
            time.sleep(0.02)

        status.write("Scraping partners...")

        partners = get_partners(
            platform,
            enrich_details=enrich_details
        )

        progress.progress(85)
        status.write("Building dataset...")

        partners_df = pd.DataFrame(partners)

        progress.progress(100)
        status.success("Scraping complete!")

        if partners_df.empty:
            st.warning("No partners found.")

        else:

            total = len(partners_df)

            website_count = (
                partners_df["website"]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
                .sum()
                if "website" in partners_df.columns
                else 0
            )

            linkedin_count = (
                partners_df["linkedin"]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
                .sum()
                if "linkedin" in partners_df.columns
                else 0
            )

            c1, c2, c3 = st.columns(3)

            c1.metric("Partners", total)
            c2.metric("Websites", website_count)
            c3.metric("LinkedIn", linkedin_count)

            st.divider()

            search = st.text_input(
                "🔍 Search Company"
            )

            filtered_df = partners_df.copy()

            if search:

                filtered_df = filtered_df[
                    filtered_df["company_name"]
                    .str.contains(search, case=False, na=False)
                ]

            col1, col2 = st.columns(2)

            with col1:
                missing_website = st.checkbox(
                    "Missing Website"
                )

            with col2:
                missing_linkedin = st.checkbox(
                    "Missing LinkedIn"
                )

            if missing_website:

                filtered_df = filtered_df[
                    filtered_df["website"]
                    .fillna("")
                    .eq("")
                ]

            if missing_linkedin:

                filtered_df = filtered_df[
                    filtered_df["linkedin"]
                    .fillna("")
                    .eq("")
                ]

            st.write(
                f"Showing **{len(filtered_df)}** partners"
            )

            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "⬇ Download Partner Dataset",
                filtered_df.to_csv(index=False).encode("utf-8"),
                "partners.csv",
                "text/csv",
                use_container_width=True
            )
import time
import pandas as pd
import streamlit as st

from directory_finder import get_partner_directories, get_partners


st.set_page_config(
    page_title="Directory-Scraper",
    
    layout="wide"
)



st.title("Directory-Scraper")


st.sidebar.header("Settings")

platform = st.sidebar.selectbox(
    "Platform",
    ["Zoho", "Microsoft", "Both"]
)

enrich_details = st.sidebar.checkbox(
    "Enrich Website & LinkedIn",
    value=True
)



directories_tab, partners_tab = st.tabs(
    [" Partner Directories", " Partners"]
)




with directories_tab:

    st.subheader("Partner Directories")

    if st.button("Fetch Directories", use_container_width=True):

        progress = st.progress(0)
        status = st.empty()

        status.write("Fetching directories...")

        for i in range(15):
            progress.progress((i + 1) * 5)
            time.sleep(0.03)

        directories = get_partner_directories(platform)

        progress.progress(100)
        status.success("Directories loaded!")

        if not directories:
            st.warning("No directories found.")

        else:

            directories_df = pd.DataFrame(directories)

            st.metric("Directories Found", len(directories_df))

            st.dataframe(
                directories_df,
                hide_index=True,
                use_container_width=True
            )

            st.download_button(
                "⬇ Download Directories CSV",
                directories_df.to_csv(index=False).encode("utf-8"),
                "partner_directories.csv",
                "text/csv",
                use_container_width=True
            )



with partners_tab:

    st.subheader("Partners")

    if st.button("Fetch Partners", use_container_width=True):

        progress = st.progress(0)
        status = st.empty()

        status.write("Initializing scraper...")

        for i in range(30):
            progress.progress(i + 1)
            time.sleep(0.02)

        status.write("Scraping partners...")

        partners = get_partners(
            platform,
            enrich_details=enrich_details
        )

        progress.progress(85)
        status.write("Building dataset...")

        partners_df = pd.DataFrame(partners)

        progress.progress(100)
        status.success("Scraping complete!")

        if partners_df.empty:
            st.warning("No partners found.")

        else:

            total = len(partners_df)

            website_count = (
                partners_df["website"]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
                .sum()
                if "website" in partners_df.columns
                else 0
            )

            linkedin_count = (
                partners_df["linkedin"]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
                .sum()
                if "linkedin" in partners_df.columns
                else 0
            )

            c1, c2, c3 = st.columns(3)

            c1.metric("Partners", total)
            c2.metric("Websites", website_count)
            c3.metric("LinkedIn", linkedin_count)

            st.divider()

            search = st.text_input(
                "🔍 Search Company"
            )

            filtered_df = partners_df.copy()

            if search:

                filtered_df = filtered_df[
                    filtered_df["company_name"]
                    .str.contains(search, case=False, na=False)
                ]

            col1, col2 = st.columns(2)

            with col1:
                missing_website = st.checkbox(
                    "Missing Website"
                )

            with col2:
                missing_linkedin = st.checkbox(
                    "Missing LinkedIn"
                )

            if missing_website:

                filtered_df = filtered_df[
                    filtered_df["website"]
                    .fillna("")
                    .eq("")
                ]

            if missing_linkedin:

                filtered_df = filtered_df[
                    filtered_df["linkedin"]
                    .fillna("")
                    .eq("")
                ]

            st.write(
                f"Showing **{len(filtered_df)}** partners"
            )

            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "⬇ Download Partner Dataset",
                filtered_df.to_csv(index=False).encode("utf-8"),
                "partners.csv",
                "text/csv",
                use_container_width=True
            )
