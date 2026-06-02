import os
import sqlite3
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


# ------------------------------------------------------------
# 1) EDIT YOUR GROUPS HERE
# Replace the placeholder teams with the real teams.
# ------------------------------------------------------------
GROUPS: Dict[str, List[str]] = {
    "Group A": ["South Korea", "South Africa", "Mexico", "Czechia"],
    "Group B": ["Team B1", "Team B2", "Team B3", "Team B4"],
    "Group C": ["Team C1", "Team C2", "Team C3", "Team C4"],
    "Group D": ["Team D1", "Team D2", "Team D3", "Team D4"],
    "Group E": ["Team E1", "Team E2", "Team E3", "Team E4"],
    "Group F": ["Team F1", "Team F2", "Team F3", "Team F4"],
    "Group G": ["Team G1", "Team G2", "Team G3", "Team G4"],
    "Group H": ["Team H1", "Team H2", "Team H3", "Team H4"],
    "Group I": ["Team I1", "Team I2", "Team I3", "Team I4"],
    "Group J": ["Team J1", "Team J2", "Team J3", "Team J4"],
    "Group K": ["Team K1", "Team K2", "Team K3", "Team K4"],
    "Group L": ["Team L1", "Team L2", "Team L3", "Team L4"],
}

DB_PATH = "worldcup_game.db"


# ------------------------------------------------------------
# 2) DATABASE
# ------------------------------------------------------------
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            player_name TEXT NOT NULL,
            group_name TEXT NOT NULL,
            pos1 TEXT NOT NULL,
            pos2 TEXT NOT NULL,
            pos3 TEXT NOT NULL,
            pos4 TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (player_name, group_name)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS official_results (
            group_name TEXT PRIMARY KEY,
            pos1 TEXT NOT NULL,
            pos2 TEXT NOT NULL,
            pos3 TEXT NOT NULL,
            pos4 TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    cur.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('submissions_open', 'yes')"
    )

    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()


def save_prediction(player_name: str, rankings: Dict[str, List[str]]):
    conn = get_connection()
    cur = conn.cursor()

    for group_name, ranking in rankings.items():
        cur.execute(
            """
            INSERT OR REPLACE INTO predictions
            (player_name, group_name, pos1, pos2, pos3, pos4, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (player_name, group_name, ranking[0], ranking[1], ranking[2], ranking[3]),
        )

    conn.commit()
    conn.close()


def save_official_results(results: Dict[str, List[str]]):
    conn = get_connection()
    cur = conn.cursor()

    for group_name, ranking in results.items():
        cur.execute(
            """
            INSERT OR REPLACE INTO official_results
            (group_name, pos1, pos2, pos3, pos4, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (group_name, ranking[0], ranking[1], ranking[2], ranking[3]),
        )

    conn.commit()
    conn.close()


def load_predictions() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM predictions", conn)
    conn.close()
    return df


def load_results() -> Dict[str, List[str]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT group_name, pos1, pos2, pos3, pos4 FROM official_results"
    ).fetchall()
    conn.close()

    return {row[0]: [row[1], row[2], row[3], row[4]] for row in rows}


# ------------------------------------------------------------
# 3) GAME LOGIC
# ------------------------------------------------------------
def score_group(prediction: List[str], official_result: List[str]) -> int:
    return sum(1 for predicted_team, real_team in zip(prediction, official_result) if predicted_team == real_team)


def calculate_leaderboard() -> pd.DataFrame:
    predictions_df = load_predictions()
    official_results = load_results()

    if predictions_df.empty:
        return pd.DataFrame(columns=["Player", "Score", "Max Score", "Groups Scored"])

    if not official_results:
        players = sorted(predictions_df["player_name"].unique())
        return pd.DataFrame(
            {
                "Player": players,
                "Score": [0] * len(players),
                "Max Score": [0] * len(players),
                "Groups Scored": [0] * len(players),
            }
        )

    rows = []

    for player_name in sorted(predictions_df["player_name"].unique()):
        player_df = predictions_df[predictions_df["player_name"] == player_name]

        total_score = 0
        groups_scored = 0

        for _, row in player_df.iterrows():
            group_name = row["group_name"]

            if group_name not in official_results:
                continue

            prediction = [row["pos1"], row["pos2"], row["pos3"], row["pos4"]]
            official_result = official_results[group_name]

            total_score += score_group(prediction, official_result)
            groups_scored += 1

        rows.append(
            {
                "Player": player_name,
                "Score": total_score,
                "Max Score": groups_scored * 4,
                "Groups Scored": groups_scored,
            }
        )

    leaderboard = pd.DataFrame(rows)
    leaderboard = leaderboard.sort_values(
        by=["Score", "Groups Scored", "Player"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    leaderboard.insert(0, "Rank", range(1, len(leaderboard) + 1))
    return leaderboard


def calculate_player_details(player_name: str) -> pd.DataFrame:
    predictions_df = load_predictions()
    official_results = load_results()

    if predictions_df.empty or player_name not in predictions_df["player_name"].unique():
        return pd.DataFrame()

    player_df = predictions_df[predictions_df["player_name"] == player_name]
    rows = []

    for _, row in player_df.iterrows():
        group_name = row["group_name"]
        prediction = [row["pos1"], row["pos2"], row["pos3"], row["pos4"]]
        official = official_results.get(group_name)

        if official is None:
            rows.append(
                {
                    "Group": group_name,
                    "Prediction": " > ".join(prediction),
                    "Official Result": "Not entered yet",
                    "Points": "",
                }
            )
        else:
            rows.append(
                {
                    "Group": group_name,
                    "Prediction": " > ".join(prediction),
                    "Official Result": " > ".join(official),
                    "Points": score_group(prediction, official),
                }
            )

    return pd.DataFrame(rows)


# ------------------------------------------------------------
# 4) STREAMLIT UI
# ------------------------------------------------------------
def admin_password_ok() -> bool:
    # For deployment, set this as an environment variable or Streamlit secret.
    # Streamlit secret name: admin_password
    try:
        password = st.secrets.get("admin_password", None)
    except Exception:
        password = None

    if not password:
        password = os.environ.get("ADMIN_PASSWORD", "change-me")

    entered = st.text_input("Admin password", type="password")
    return entered == password


def ranking_input(group_name: str, teams: List[str], key_prefix: str) -> Tuple[bool, List[str]]:
    st.markdown(f"#### {group_name}")

    ranking = []
    available = teams.copy()
    valid = True

    for position in range(1, 5):
        choice = st.selectbox(
            f"{group_name} - Position {position}",
            options=["Select a team"] + available,
            key=f"{key_prefix}_{group_name}_{position}",
        )

        if choice == "Select a team":
            valid = False
        else:
            ranking.append(choice)
            available.remove(choice)

    return valid, ranking


def submit_prediction_page():
    st.header("Submit your group rankings")

    submissions_open = get_setting("submissions_open", "yes") == "yes"

    if not submissions_open:
        st.warning("Submissions are currently closed.")
        return

    player_name = st.text_input("Your name", placeholder="Example: Kaan")

    st.info("Choose the order you think each group will finish. You get 1 point for every exact position you guess correctly.")

    rankings = {}
    all_valid = True

    for group_name, teams in GROUPS.items():
        with st.expander(group_name, expanded=(group_name == "Group A")):
            valid, ranking = ranking_input(group_name, teams, "prediction")
            if not valid:
                all_valid = False
            else:
                rankings[group_name] = ranking

    if st.button("Submit my predictions", type="primary"):
        if not player_name.strip():
            st.error("Please enter your name.")
        elif not all_valid or len(rankings) != len(GROUPS):
            st.error("Please complete every group.")
        else:
            save_prediction(player_name.strip(), rankings)
            st.success("Your predictions were saved!")


def leaderboard_page():
    st.header("Leaderboard")

    leaderboard = calculate_leaderboard()

    if leaderboard.empty:
        st.info("No predictions yet.")
        return

    st.dataframe(leaderboard, hide_index=True, use_container_width=True)

    predictions_df = load_predictions()
    players = sorted(predictions_df["player_name"].unique()) if not predictions_df.empty else []

    if players:
        player = st.selectbox("See detailed score for a player", players)
        details = calculate_player_details(player)
        if not details.empty:
            st.dataframe(details, hide_index=True, use_container_width=True)


def admin_page():
    st.header("Admin")

    if not admin_password_ok():
        st.warning("Enter the admin password to manage the game.")
        return

    st.success("Admin mode unlocked.")

    submissions_open = get_setting("submissions_open", "yes") == "yes"
    new_status = st.toggle("Allow friends to submit predictions", value=submissions_open)

    if new_status != submissions_open:
        set_setting("submissions_open", "yes" if new_status else "no")
        st.success("Submission status updated.")

    st.subheader("Enter official group results")
    st.caption("You can enter results group by group after the matches finish.")

    results = {}
    all_valid = True

    for group_name, teams in GROUPS.items():
        with st.expander(group_name, expanded=False):
            valid, ranking = ranking_input(group_name, teams, "official")
            if valid:
                results[group_name] = ranking
            else:
                all_valid = False

    if st.button("Save official results", type="primary"):
        if not results:
            st.error("Please enter at least one complete group result.")
        else:
            save_official_results(results)
            st.success("Official results saved. The leaderboard has been updated.")

    st.subheader("All predictions")
    predictions_df = load_predictions()
    if predictions_df.empty:
        st.info("No predictions submitted yet.")
    else:
        st.dataframe(predictions_df, hide_index=True, use_container_width=True)


def main():
    st.set_page_config(page_title="World Cup Ranking Guessing Game", page_icon="⚽", layout="wide")
    init_db()

    st.title("⚽ World Cup Ranking Guessing Game")
    st.write("Guess the exact final ranking of each group. Correct team + correct position = 1 point.")

    tab1, tab2, tab3 = st.tabs(["Submit Prediction", "Leaderboard", "Admin"])

    with tab1:
        submit_prediction_page()

    with tab2:
        leaderboard_page()

    with tab3:
        admin_page()


if __name__ == "__main__":
    main()
