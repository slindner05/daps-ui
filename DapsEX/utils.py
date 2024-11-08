from Payloads.poster_renamerr_payload import Payload as PosterRenamerPayload
from Payloads.unmatched_assets_payload import Payload as UnmatchedAssetsPayload
from DapsEX.media import Radarr, Server, Sonarr
import re
from logging import Logger


def get_combined_media_lists(
    radarr_instances: dict[str, Radarr], sonarr_instances: dict[str, Sonarr]
) -> tuple[list, list]:
    all_movies = []
    combined_series_dict = {}
    for radarr in radarr_instances.values():
        all_movies.extend(radarr.movies)
    for sonarr in sonarr_instances.values():
        for series in sonarr.series:
            series_title = series["title"]
            if series_title not in combined_series_dict:
                combined_series_dict[series_title] = series
            else:
                existing_series = combined_series_dict[series_title]

                existing_seasons_lookup = {
                    season['season']: season for season in existing_series.get("seasons", [])
                }
                for season in series.get("seasons", []):
                    season_number = season['season']
                    if season_number in existing_seasons_lookup:
                        if season.get("has_episodes", False):
                            existing_seasons_lookup[season_number]["has_episodes"] = True
                    else:
                        existing_seasons_lookup[season_number] = season
                combined_series_dict[series_title]["seasons"] = list(existing_seasons_lookup.values())

    all_series = list(combined_series_dict.values())
    return all_movies, all_series


def get_combined_collections_lists(
    plex_instances: dict[str, Server]
) -> tuple[list, list]:
    all_movie_collections = []
    all_series_collections = []
    for plex in plex_instances.values():
        all_movie_collections.extend(plex.movie_collections)
        all_series_collections.extend(plex.series_collections)
    return all_movie_collections, all_series_collections


def create_arr_instances(
    payload_class: PosterRenamerPayload | UnmatchedAssetsPayload, radarr_class: type[Radarr], sonarr_class: type[Sonarr], logger: Logger,
) -> tuple[dict[str, Radarr], dict[str, Sonarr]]:
    radarr_instances: dict[str, Radarr] = {}
    sonarr_instances: dict[str, Sonarr] = {}

    for key, value in payload_class.radarr.items():
        if key in payload_class.instances:
            radarr_name = f"{key}"
            radarr_instances[radarr_name] = radarr_class(
                base_url=value["url"], api=value["api"], logger=logger
            )
    for key, value in payload_class.sonarr.items():
        if key in payload_class.instances:
            sonarr_name = f"{key}"
            sonarr_instances[sonarr_name] = sonarr_class(
                base_url=value["url"], api=value["api"], logger=logger
            )
    return radarr_instances, sonarr_instances


def create_plex_instances(
    payload: PosterRenamerPayload | UnmatchedAssetsPayload, plex_class: type[Server], logger: Logger
) -> dict[str, Server]:
    plex_instances = {}
    for key, value in payload.plex.items():
        if key in payload.instances:
            plex_name = f"{key}"
            plex_instances[plex_name] = plex_class(
                plex_url=value["url"],
                plex_token=value["api"],
                library_names=payload.library_names,
                logger=logger
            )
    return plex_instances

def remove_chars(file_name: str) -> str:
    file_name = re.sub(r"(?<=\w)-\s", " ", file_name)
    file_name = re.sub(r"(?<=\w)\s-\s", " ", file_name)
    file_name = re.sub(r"[\*\^;~\\`\[\]'\"\/,.!?:_…]", "", file_name)
    file_name = remove_emojis(file_name)
    return file_name.strip().replace("&", "and").replace("\u00A0", ' ').lower()

def strip_id(name: str) -> str:
    """
    Strip tvdb/imdb/tmdb ID from movie title.
    """
    return re.sub(r"\s*\{.*\}", "", name)

def remove_emojis(name: str) -> str:
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols, etc.
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002700-\U000027BF"  # Dingbats
        "\U0001F1E0-\U0001F1FF"  # Flags
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", name)

def strip_year(name: str) -> str:
    return re.sub(r"\(\d{4}\)", "", name).strip()
