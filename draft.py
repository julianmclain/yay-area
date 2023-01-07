import os
import csv
import json
from typing import List, Dict
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
from yfpy import Data
from yfpy.query import YahooFantasySportsQuery


DRAFT_FILENAME = 'draft-2022.csv'
PLAYER_DATA_FILENAME = 'player-stats-2022.json'
ANALYSIS_FILENAME = 'draft-analysis-2022.json'
TEMPLATE_FILENAME = 'template.html'
HTML_FILENAME = 'index.html'


LEAGUE_ID = '782339'
GAME_CODE = "nfl"
AUTH_DIR = Path(__file__).parent


PlayerId = str
TeamName = str


@dataclass
class DraftPick:
    id: str
    team_name: str
    first_name: str
    last_name: str
    overall_pick: int


@dataclass
class YahooPlayerData:
    id: str
    position: str
    season_points: float

    @staticmethod
    def from_json_string(data: str):
        dict_data = json.loads(data)
        return YahooPlayerData(dict_data['id'], dict_data['position'], dict_data['season_points'])

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__)


@dataclass
class PlayerAnalysis:
    id: str
    team_name: str
    first_name: str
    last_name: str
    position: str
    overall_pick: int
    season_points: float
    draft_position_rank: int
    season_end_position_rank: int
    differential: int


def read_draft(filename: str) -> List[DraftPick]:
    draft = []

    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            pick = DraftPick(row['Player ID'], row['Team Name'], row['First Name'], row['Last Name'], int(row['Pick']))
            draft.append(pick)
    
    return draft 


def fetch_and_write_yahoo_data(draft_picks: List[DraftPick]) -> None:
    yahoo_data = _fetch_yahoo_player_data(draft_picks)
    _write_yahoo_data(PLAYER_DATA_FILENAME, yahoo_data)
    print(f'Successfully stored {len(yahoo_data)} yahoo player records locally!')


def _fetch_yahoo_player_data(draft_picks: List[DraftPick]) -> Dict[PlayerId, YahooPlayerData]:
    """
    Uses yahoo fantasy api wrapper to fetch player data. No error handling, so a single failure
    will kill the script. Rerun script when this happens, No partial restart.

    https://github.com/uberfastman/yfpy

    returns a dict of player id -> player data
    """
    player_data = {}
    yahoo_query = _create_yahoo_query()

    for player in draft_picks:
        response = yahoo_query.get_player_stats_for_season(player.id)
        player_data[player.id] = YahooPlayerData(player.id, response.primary_position, response.player_points_value)

    return player_data


def _create_yahoo_query() -> YahooFantasySportsQuery:
    load_dotenv()

    return YahooFantasySportsQuery(
        AUTH_DIR,
        LEAGUE_ID,
        game_code=GAME_CODE,
        offline=False,
        all_output_as_json_str=False,
        consumer_key=os.environ['YFPY_CONSUMER_KEY'],
        consumer_secret=os.environ['YFPY_CONSUMER_SECRET'],
        browser_callback=True
    )


def _write_yahoo_data(filename: str, data: Dict[PlayerId, YahooPlayerData]) -> None:
    json_data = {k: v.to_json() for k, v in data.items()}

    with open(filename, 'w') as f:
        json.dump(json_data, f)


def read_yahoo_data(filename: str) -> Dict[PlayerId, YahooPlayerData]:
    player_data = {}

    with open(filename) as f:
        data = json.load(f)
        for player_id, player_data_str in data.items():
            player = YahooPlayerData.from_json_string(player_data_str)
            player_data[player_id] = player 
        return player_data


def get_player_analysis(draft_picks: List[DraftPick], player_data: Dict[PlayerId, YahooPlayerData]) -> List[PlayerAnalysis]:
    player_analysis_list = []
    curr_draft_player_position_ranks = defaultdict(lambda: 1)
    player_season_points_ranks = _get_player_position_season_point_ranks(player_data)

    for pick in draft_picks:
        # Get draft position rank
        position = player_data[pick.id].position
        draft_position_rank = curr_draft_player_position_ranks[position]
        curr_draft_player_position_ranks[position] += 1

        season_points = player_data[pick.id].season_points
        season_points_position_rank = player_season_points_ranks[pick.id]
        player_analysis = PlayerAnalysis(pick.id, pick.team_name, pick.first_name, pick.last_name, position, pick.overall_pick, season_points, draft_position_rank, season_points_position_rank, draft_position_rank - season_points_position_rank)
        player_analysis_list.append(player_analysis)

    return player_analysis_list 


def _get_player_position_season_point_ranks(player_data: Dict[PlayerId, YahooPlayerData]) -> Dict[PlayerId, int]:
    player_position_ranks = {}
    curr_position_ranks = {
        'QB': 1,
        'RB': 1,
        'WR': 1,
        'TE': 1,
        'K': 1,
        'DEF': 1
    }
    players_sorted = sorted(player_data.values(), key=lambda player_data: player_data.season_points, reverse=True)

    for player in players_sorted:
        player_position_ranks[player.id] = curr_position_ranks[player.position]
        curr_position_ranks[player.position] += 1

    return player_position_ranks


def get_players_by_team(players: List[PlayerAnalysis]) -> Dict[TeamName, List[PlayerAnalysis]]:
    teams = defaultdict(list)
    for player in players:
        teams[player.team_name].append(player)

    for team in teams:
        teams[team].sort(key=lambda player: player.overall_pick)

    return teams


def get_team_differentials(players: List[PlayerAnalysis]) -> Dict[TeamName, int]:
    team_differentials = defaultdict(lambda: 0)

    for player in players:
        team_differentials[player.team_name] += player.differential

    return team_differentials


def render_html(teams: Dict[TeamName, List[PlayerAnalysis]], players: List[PlayerAnalysis], draft_picks: List[DraftPick], team_differentials: Dict[TeamName, int]) -> str:
    environment = Environment(loader=FileSystemLoader('./'))
    template = environment.get_template(TEMPLATE_FILENAME)
    content = template.render(
        draft_picks=draft_picks,
        players=players,
        teams=teams,
        team_differentials=team_differentials
    )
    return content


def write_html(html: str) -> None:
    with open(HTML_FILENAME, 'w') as f:
        f.write(html)


def render_and_write_html(draft_picks: List[DraftPick], teams: Dict[TeamName, List[PlayerAnalysis]], players: List[PlayerAnalysis], team_differentials: Dict[TeamName, int]) -> None:
    html = render_html(teams, players, draft_picks, team_differentials)
    write_html(html)

 
if __name__ == '__main__':
    draft_picks = read_draft(DRAFT_FILENAME)
    # If running for the first time, uncomment the call to fetch_and_write_yahoo_data
    # fetch_and_write_yahoo_data(draft_picks)
    yahoo_player_data = read_yahoo_data(PLAYER_DATA_FILENAME)
    players = get_player_analysis(draft_picks, yahoo_player_data)
    teams = get_players_by_team(players)
    team_differentials = get_team_differentials(players)
    render_and_write_html(draft_picks, teams, players, team_differentials)
