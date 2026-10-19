import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

STEAM_ID = "76561199223848682"
API_KEY = os.environ["STEAM_API_KEY"]
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "steam-data.json"

# Steam App IDs for the 25 games in the challenge.
GAMES = [
    (254700, "Resident Evil 4 (2005)"),
    (233290, "MURDERED: SOUL SUSPECT"),
    (601360, "Portal: Revolution"),
    (204450, "Call of Juarez: Gunslinger"),
    (1687950, "Persona 5 Royal"),
    (48000, "LIMBO"),
    (50130, "Mafia II (Classic)"),
    (349040, "Naruto Shippuden: Ultimate Ninja Storm 4"),
    (883710, "Resident Evil 2"),
    (307690, "Sleeping Dogs: Definitive Edition"),
    (1817230, "Hi-Fi RUSH"),
    (610370, "Desperados III"),
    (1091500, "Cyberpunk 2077"),
    (489830, "Skyrim Special Edition"),
    (1382330, "Persona 5 Strikers"),
    (397540, "Borderlands 3"),
    (22490, "Fallout: New Vegas (PCR)"),
    (2369390, "Far Cry 6"),
    (2427410, "S.T.A.L.K.E.R.: Shadow of Chornobyl Enhanced Edition"),
    (847370, "Sunset Overdrive"),
    (544750, "Soulcalibur VI"),
    (389730, "Tekken 7"),
    (1420290, "No More Heroes"),
    (105600, "Terraria"),
    (525480, ".hack//G.U. Last Recode"),
]

# Cross-checked totals from Steam Community achievement pages.
# Games omitted here remain unverified until their published total is checked.
VERIFIED_TOTALS = {
    254700: 12,       # Resident Evil 4 (2005)
    233290: 48,       # MURDERED: SOUL SUSPECT
    601360: 21,       # Portal: Revolution
    204450: 26,       # Call of Juarez: Gunslinger
    1687950: 53,      # Persona 5 Royal
    48000: 13,        # LIMBO
    50130: 67,        # Mafia II (Classic)
    349040: 53,       # Naruto Shippuden: Ultimate Ninja STORM 4
    883710: 44,       # Resident Evil 2
    307690: 59,       # Sleeping Dogs: Definitive Edition
    1817230: 71,      # Hi-Fi RUSH
    610370: 36,       # Desperados III
    1091500: 57,      # Cyberpunk 2077
    489830: 75,       # Skyrim Special Edition
    1382330: 47,      # Persona 5 Strikers
    397540: 81,       # Borderlands 3
    22490: 75,        # Fallout: New Vegas PCR
    2369390: 99,      # Far Cry 6
    847370: 80,       # Sunset Overdrive
    389730: 42,       # Tekken 7
    1420290: 20,      # No More Heroes
    105600: 137,      # Terraria
    525480: 52,       # .hack//G.U. Last Recode
}

def steam_json(endpoint, params):
    params = {"key": API_KEY, **params}
    url = "https://api.steampowered.com/" + endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "AchievementWinter/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))

def main():
    owned_response = steam_json(
        "IPlayerService/GetOwnedGames/v1/",
        {"steamid": STEAM_ID, "include_appinfo": "true", "include_played_free_games": "true"},
    )
    owned_games = owned_response.get("response", {}).get("games", [])
    owned = {game["appid"]: game for game in owned_games}
    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "steam_id": STEAM_ID,
        "games": {},
    }

    for app_id, title in GAMES:
        item = {
            "appid": app_id,
            "name": title,
            "owned": app_id in owned,
            "playtime_minutes": owned.get(app_id, {}).get("playtime_forever"),
            "playtime_hours": round(owned[app_id]["playtime_forever"] / 60, 1) if app_id in owned else None,
            "achievements_unavailable": False,
            "achievements_earned": None,
            "achievements_total": None,
            "player_achievements_total": None,
            "schema_achievements_total": None,
            "achievement_counts_match": None,
            "dlc_scope_verified": False,
            "achievement_percent": None,
            "error": None,
        }
        try:
            stats = steam_json(
                "ISteamUserStats/GetPlayerAchievements/v1/",
                {"steamid": STEAM_ID, "appid": app_id, "l": "en"},
            ).get("playerstats", {})
            if stats.get("success") is False:
                item["achievements_unavailable"] = True
                item["error"] = stats.get("error", "Steam stats are not available for this game")
            else:
                achievements = stats.get("achievements", [])
                item["player_achievements_total"] = len(achievements)
                item["achievements_earned"] = sum(1 for a in achievements if int(a.get("achieved", 0)) == 1)
                try:
                    schema = steam_json("ISteamUserStats/GetSchemaForGame/v2/", {"appid": app_id, "l": "en"}).get("game", {}).get("availableGameStats", {})
                    schema_achievements = schema.get("achievements", [])
                    if schema_achievements:
                        item["schema_achievements_total"] = len(schema_achievements)
                        item["achievements_total"] = len(schema_achievements)
                        item["achievement_counts_match"] = len(achievements) == len(schema_achievements)
                    else:
                        item["achievements_total"] = len(achievements)
                except Exception:
                    item["achievements_total"] = len(achievements)
                total = item["achievements_total"]
                expected_total = VERIFIED_TOTALS.get(app_id)
                item["dlc_scope_verified"] = (
                    expected_total is not None
                    and item["schema_achievements_total"] == expected_total
                    and item["achievement_counts_match"] is True
                )
                if expected_total is not None and item["schema_achievements_total"] != expected_total:
                    item["error"] = (
                        f"Steam schema total differs from verified reference: "
                        f"{item['schema_achievements_total']} vs {expected_total}"
                    )
                item["achievement_percent"] = round(100 * item["achievements_earned"] / total, 1) if total else None
                if not achievements:
                    item["achievements_unavailable"] = True
                    item["error"] = "Steam returned no achievement records"
                elif item["achievement_counts_match"] is False:
                    item["error"] = "Player achievement list differs from full schema; review required"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            try:
                error_data = json.loads(body)
                detail = error_data.get("playerstats", {}).get("error")
            except (json.JSONDecodeError, AttributeError):
                detail = None
            item["achievements_unavailable"] = True
            item["error"] = f"HTTP {exc.code}: {detail or exc.reason}"[:240]
        except Exception as exc:
            item["achievements_unavailable"] = True
            item["error"] = str(exc)[:240]
        result["games"][str(app_id)] = item
        time.sleep(0.15)

    # Avoid creating a Git commit every 15 minutes when the data has not changed.
    try:
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = {}

    if previous.get("games") == result["games"]:
        result["updated_at"] = previous.get("updated_at")
        print("Steam data is unchanged; keeping the existing timestamp.")
        return

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    available = sum(1 for game in result["games"].values() if game["achievements_total"] is not None)
    print(f"Wrote {OUTPUT.name}: {available}/{len(GAMES)} games returned achievement data.")

if __name__ == "__main__":
    main()
