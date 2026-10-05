import json
import math
from datetime import datetime, timezone
from typing import Dict, List

import pandas as pd
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="IG Following Review",
    page_icon="📱",
    layout="centered",
    initial_sidebar_state="collapsed",
)

STATUS_LABELS = {
    "pending": "Pending",
    "keep": "Keep",
    "unfollowed": "Unfollowed",
    "later": "Later",
}
VALID_STATUSES = set(STATUS_LABELS)


@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def owner_id() -> str:
    return str(st.secrets.get("OWNER_ID", "default-owner"))


#def require_login() -> None:
    expected = str(st.secrets.get("APP_PASSWORD", ""))
    if not expected:
        st.error("APP_PASSWORD is missing from Streamlit secrets.")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("IG Following Review")
    st.caption("Private review tool for your Instagram following list")
    password = st.text_input("App password", type="password")
    if st.button("Unlock", use_container_width=True, type="primary"):
        if password == expected:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()


def parse_following_json(uploaded_file) -> List[Dict]:
    raw = json.load(uploaded_file)
    rows = raw.get("relationships_following", [])
    deduped: Dict[str, Dict] = {}

    for item in rows:
        username = str(item.get("title") or "").strip()
        data = item.get("string_list_data") or []
        first = data[0] if data else {}
        href = str(first.get("href") or "").strip()
        timestamp = first.get("timestamp")

        if not username and href:
            username = href.rstrip("/").split("/")[-1]
        if not username:
            continue

        profile_url = f"https://www.instagram.com/{username}/"
        if href and "instagram.com" in href:
            profile_url = href.replace("instagram.com/_u/", "instagram.com/")
            if not profile_url.endswith("/"):
                profile_url += "/"

        deduped[username.lower()] = {
            "owner_id": owner_id(),
            "username": username,
            "profile_url": profile_url,
            "followed_at": int(timestamp) if isinstance(timestamp, (int, float)) else None,
        }

    return list(deduped.values())


def fetch_all_profiles() -> List[Dict]:
    db = get_supabase()
    results: List[Dict] = []
    page_size = 1000
    offset = 0
    while True:
        resp = (
            db.table("ig_following_reviews")
            .select("username,profile_url,followed_at,status,updated_at")
            .eq("owner_id", owner_id())
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        results.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return results


def import_profiles(rows: List[Dict]) -> int:
    db = get_supabase()
    existing = {r["username"].lower(): r for r in fetch_all_profiles()}
    now = datetime.now(timezone.utc).isoformat()

    prepared = []
    for row in rows:
        old = existing.get(row["username"].lower())
        prepared.append(
            {
                **row,
                "status": (old or {}).get("status", "pending"),
                "updated_at": (old or {}).get("updated_at", now),
            }
        )

    batch_size = 500
    for start in range(0, len(prepared), batch_size):
        db.table("ig_following_reviews").upsert(
            prepared[start : start + batch_size],
            on_conflict="owner_id,username",
        ).execute()

    st.cache_data.clear()
    return len(prepared)


def set_status(username: str, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError("Invalid status")
    get_supabase().table("ig_following_reviews").update(
        {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("owner_id", owner_id()).eq("username", username).execute()


@st.cache_data(ttl=8)
def cached_profiles(owner: str) -> List[Dict]:
    return fetch_all_profiles()


def followed_date(ts):
    if not ts:
        return "Unknown"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%d %b %Y")
    except Exception:
        return "Unknown"


def export_dataframe(rows: List[Dict]) -> pd.DataFrame:
    data = []
    for r in rows:
        data.append(
            {
                "username": r["username"],
                "status": r.get("status", "pending"),
                "profile_url": r.get("profile_url", ""),
                "followed_date": followed_date(r.get("followed_at")),
                "followed_at": r.get("followed_at"),
                "updated_at": r.get("updated_at"),
            }
        )
    return pd.DataFrame(data)


def status_counts(rows: List[Dict]) -> Dict[str, int]:
    counts = {k: 0 for k in VALID_STATUSES}
    for row in rows:
        status = row.get("status", "pending")
        counts[status if status in counts else "pending"] += 1
    return counts


def sort_rows(rows: List[Dict], mode: str) -> List[Dict]:
    if mode == "Newest followed first":
        return sorted(rows, key=lambda x: x.get("followed_at") or 0, reverse=True)
    if mode == "Oldest followed first":
        return sorted(rows, key=lambda x: x.get("followed_at") or 0)
    if mode == "Username A-Z":
        return sorted(rows, key=lambda x: x.get("username", "").lower())
    return rows


def profile_card(profile: Dict, index: int, total: int) -> None:
    username = profile["username"]
    first_char = username[0].upper() if username else "?"

    st.markdown(
        f"""
        <div style="text-align:center; padding: 12px 0 2px 0;">
          <div style="width:92px;height:92px;border-radius:50%;margin:0 auto 12px auto;display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:700;background:rgba(128,128,128,.12);border:1px solid rgba(128,128,128,.25);">{first_char}</div>
          <div style="font-size:27px;font-weight:700;word-break:break-word;">@{username}</div>
          <div style="opacity:.72;margin-top:6px;">Following since {followed_date(profile.get('followed_at'))}</div>
          <div style="opacity:.58;margin-top:3px;">Account {index:,} of {total:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.link_button(
        "Open Instagram Profile ↗",
        profile.get("profile_url") or f"https://www.instagram.com/{username}/",
        use_container_width=True,
        type="primary",
    )

    col1, col2 = st.columns(2)
    if col1.button("✓ KEEP", use_container_width=True, key=f"keep_{username}"):
        set_status(username, "keep")
        st.cache_data.clear()
        st.rerun()
    if col2.button("UNFOLLOWED", use_container_width=True, key=f"unfollow_{username}"):
        set_status(username, "unfollowed")
        st.cache_data.clear()
        st.rerun()

    if st.button("LATER", use_container_width=True, key=f"later_{username}"):
        set_status(username, "later")
        st.cache_data.clear()
        st.rerun()


# require_login()

st.title("IG Following Review")
st.caption("Review manually in Instagram. Progress is saved to Supabase after every action.")

with st.sidebar:
    st.subheader("Account")
    if st.button("Lock app", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

    st.divider()
    st.subheader("Import / update")
    uploaded = st.file_uploader("following.json", type=["json"], key="sidebar_upload")
    if uploaded is not None and st.button("Import following list", use_container_width=True):
        try:
            parsed = parse_following_json(uploaded)
            if not parsed:
                st.error("No accounts found in this JSON file.")
            else:
                with st.spinner("Saving accounts to Supabase..."):
                    count = import_profiles(parsed)
                st.success(f"Saved {count:,} accounts. Existing review statuses were preserved.")
                st.rerun()
        except Exception as exc:
            st.error(f"Could not import the file: {exc}")

rows = cached_profiles(owner_id())

if not rows:
    st.info("No following list has been saved yet. Upload your Instagram following.json below.")
    uploaded = st.file_uploader("Choose following.json", type=["json"], key="main_upload")
    if uploaded is not None:
        try:
            preview = parse_following_json(uploaded)
            st.write(f"Found **{len(preview):,}** unique accounts.")
            if st.button("Save to cloud storage", type="primary", use_container_width=True):
                with st.spinner("Saving to Supabase..."):
                    count = import_profiles(preview)
                st.success(f"Saved {count:,} accounts.")
                st.rerun()
        except Exception as exc:
            st.error(f"Could not read this JSON file: {exc}")
    st.stop()

counts = status_counts(rows)
reviewed = len(rows) - counts["pending"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", f"{len(rows):,}")
c2.metric("Reviewed", f"{reviewed:,}")
c3.metric("Unfollowed", f"{counts['unfollowed']:,}")
c4.metric("Remaining", f"{counts['pending']:,}")

progress_value = reviewed / len(rows) if rows else 0
st.progress(progress_value, text=f"{progress_value:.1%} reviewed")

with st.expander("Filters, search & export"):
    filter_status = st.selectbox(
        "Show",
        ["Pending", "Later", "Keep", "Unfollowed", "All"],
        index=0,
    )
    sort_mode = st.selectbox(
        "Sort",
        ["Newest followed first", "Oldest followed first", "Username A-Z"],
    )
    search_text = st.text_input("Search username", placeholder="e.g. travel...")

    df = export_dataframe(rows)
    st.download_button(
        "Download progress CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="instagram_following_review_progress.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if st.button("Refresh from cloud", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

status_map = {
    "Pending": "pending",
    "Later": "later",
    "Keep": "keep",
    "Unfollowed": "unfollowed",
}

filtered = rows
if filter_status != "All":
    target = status_map[filter_status]
    filtered = [r for r in filtered if r.get("status", "pending") == target]
if search_text.strip():
    needle = search_text.strip().lower()
    filtered = [r for r in filtered if needle in r.get("username", "").lower()]
filtered = sort_rows(filtered, sort_mode)

if not filtered:
    if filter_status == "Pending" and not search_text.strip():
        st.success("🎉 You have reviewed every saved account.")
    else:
        st.info("No accounts match the current filter.")
    st.stop()

if "card_offset" not in st.session_state:
    st.session_state.card_offset = 0
if st.session_state.card_offset >= len(filtered):
    st.session_state.card_offset = 0

current = filtered[st.session_state.card_offset]
profile_card(current, st.session_state.card_offset + 1, len(filtered))

nav1, nav2 = st.columns(2)
if nav1.button("← Previous", use_container_width=True, disabled=len(filtered) <= 1):
    st.session_state.card_offset = (st.session_state.card_offset - 1) % len(filtered)
    st.rerun()
if nav2.button("Next →", use_container_width=True, disabled=len(filtered) <= 1):
    st.session_state.card_offset = (st.session_state.card_offset + 1) % len(filtered)
    st.rerun()

st.divider()
st.caption(
    "The app never unfollows anyone automatically and never asks for your Instagram password. "
    "It only stores the exported username/profile data and your review status."
)
