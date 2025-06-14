import os
from typing import Tuple
from time import sleep
from colorama import Fore, Style

# from utils.chatbot.ai_v3 import AIPlayer
from utils.chatbot.ai_v5 import AIPlayer
from utils.logging_utils import MasterLogger
from utils.states import GameState, ScreenEnum, PlayerState
from utils.file_io import SequentialAssigner, load_players_from_lobby, save_player_to_lobby_file, synchronize_start_time
from utils.constants import (
    COLORS_INDEX_PATH, COLORS_PATH, NAMES_PATH, NAMES_INDEX_PATH, 
    # COLORS_PATH, COLORS_INDEX_PATH, COLOR_DICT
)
# from utils.asthetics import clear_screen # ,print_color

class PlayerSetup:
    """
    Handles the player setup process, including collecting player information,
    assigning a code name and color, and creating a PlayerState object.
    """

    def __init__(
        self,
        names_path=NAMES_PATH,
        names_index_path=NAMES_INDEX_PATH,
        colors_path=COLORS_PATH,
        colors_index_path=COLORS_INDEX_PATH
    ):
        """
        Initializes the PlayerSetup object with necessary paths for name and color assignment.

        Args:
            names_path (str): Path to the file containing player names.
            names_index_path (str): Path to the file tracking the current name index.
            colors_path (str): Path to the file containing color names.
            colors_index_path (str): Path to the file tracking the current color index.
        """
        self.data = {}
        self.code_name_assigner = SequentialAssigner(names_path, names_index_path, "code_names")
        self.color_assigner = SequentialAssigner(colors_path, colors_index_path, "colors")

    def prompt_input(self, field_name: str, prompt: str) -> None:
        """Prompt for a generic input and ensure it is not empty."""
        while True:
            value = input(Fore.CYAN + prompt + " " + Style.RESET_ALL).strip()
            if value:
                self.data[field_name] = value
                return
            # print_color(f"{field_name} cannot be empty.", "RED")
            print(Fore.RED + f"{field_name} cannot be empty." + Style.RESET_ALL)

    def prompt_number(self, lower: int, upper: int, prompt: str, field_name: str) -> None:
        '''
        Prompt for a number within a specified range and ensure it is valid.
        We use this to collect lobby number, number of players, and grade.
        Args:
            lower (int): The lower bound of the valid range.
            upper (int): The upper bound of the valid range.
            prompt (str): The prompt message to display to the user.
            field_name (str): The name of the field to store the value in self.data.
        '''
        while True:
            try:
                value = int(input(Fore.CYAN + f"{prompt} ({lower} - {upper}): " + Style.RESET_ALL))
                if lower <= value <= upper:
                    self.data[field_name] = value
                    return
                print(Fore.RED + f"Please enter a number between {lower} and {upper}." + Style.RESET_ALL)
            except ValueError:
                print(Fore.RED + "Invalid input. Please enter a valid number." + Style.RESET_ALL)

    def prompt_initial(self) -> None:
        '''
        Prompt for the player's last initial and ensure it is a single letter (A–Z).
        '''
        while True:
            value = input(Fore.CYAN + "Enter your last initial (A–Z): " + Style.RESET_ALL).strip().upper()
            if len(value) == 1 and value.isalpha():
                self.data["last_initial"] = value
                return
            print(Fore.RED + "Invalid input. Please enter a single letter (A–Z)." + Style.RESET_ALL)

    def run(self, gs:GameState) -> Tuple[ScreenEnum, GameState, PlayerState]:
        """
        Executes the interactive player setup process and initializes player state for the game.

        This method prompts the user to enter personal details (e.g., name, favorite food, hobby),
        assigns a unique code name and color, creates a PlayerState object, and links an AI doppelganger
        that mimics the player. It also sets up file paths in the GameState for the current lobby,
        including the chat log, voting data, and start time file.

        Args:
            gs (GameState): The current game state object that holds shared state across players.

        Returns:
            Tuple[ScreenEnum, GameState, PlayerState]: 
                screen enum that directs us to the CHAT phase,
                The updated GameState with player-specific file paths and player count,
                PlayerState for the current human player.
        """

        # prompt the player for their information
        self.prompt_number(1, 10000, "Enter your lobby number", "lobby")
        self.prompt_number(1, 5, "How many people are you playing with?", "number_of_human_players") # TODO change back to 3,5
        self.prompt_number(6, 8, "What grade are you in?", "grade")
        self.prompt_input("first_name", "Enter your first name: ")
        self.prompt_initial()
        self.prompt_input("favorite_food", "One of your favorite foods: ")
        self.prompt_input("favorite_animal", "One of your favorite_animals: ")
        self.prompt_input("hobby", "One of your hobbies? ")
        self.prompt_input("extra_info", "Tell us one more thing about you: ")

        # clear_screen()
        print(Fore.GREEN + "✅ Player setup complete." + Style.RESET_ALL)

        lobby_path = os.path.join(
            "data", "runtime", "lobbies",
            f"lobby_{self.data['lobby']}"
        )
        gs.chat_log_path = os.path.join(lobby_path, "chat_log.txt")
        gs.start_time_path = os.path.join(lobby_path, "starttime.txt")
        gs.voting_path = os.path.join(lobby_path, "voting.json")
        gs.player_path = os.path.join(lobby_path, "players.json")
        gs.number_of_human_players = self.data["number_of_human_players"]

        # Create the PlayerState object
        code_name = self.code_name_assigner.assign()
        color_name = self.color_assigner.assign()
        # for k, v in self.data.items():
            # print(k, v)
        ps = PlayerState(
            lobby_id=self.data["lobby"],
            first_name=self.data["first_name"],
            last_initial=self.data["last_initial"],
            grade=self.data["grade"],
            code_name=code_name,
            favorite_food=self.data["favorite_food"],
            favorite_animal=self.data["favorite_animal"],
            hobby=self.data["hobby"],
            extra_info=self.data["extra_info"],
            is_human=True,
            color_name=color_name,
        )
        save_player_to_lobby_file(ps)
        ps.logger = MasterLogger.get_instance()
        ps.logger.info(f"Player {ps.first_name} {ps.last_initial}. initialized with code_name: {code_name}")
        # ps.logger.info(f"Player {ps.code_name} initialized with color: {picked_color_name}")

        # NEEDS TO GO LAST
        ps.ai_doppleganger = AIPlayer(
            player_to_steal=ps
        )
        return ps, gs, ps

def collect_player_data(ss: ScreenEnum, gs: GameState, ps: PlayerState) -> Tuple[ScreenEnum, GameState, PlayerState]:
    """
    Handles the full player setup and synchronization process before transitioning to the chat phase.

    This function:
    - Prompts the current user (using PlayerSetup.run()) for setup information if their PlayerState has not yet been written.
    - Initializes a corresponding AI doppelgänger for the player.
    - Saves both the human player and AI to the lobby file.
    - Waits until all human players have joined the lobby and their data has been saved.
    - Synchronizes the shared game start time.
    - Finalizes and sorts the list of players in the GameState.

    Args:
        ss (ScreenEnum): The current screen state (not modified in this function).
        gs (GameState): The shared game state object that tracks lobby-wide data.
        ps (PlayerState): The current player's state, which may be initialized or updated.

    Returns:
        Tuple[ScreenEnum, GameState, PlayerState]: The next screen state (CHAT),
        the updated GameState with all players loaded, and the finalized PlayerState for the current user.
    """
    # clear_screen()
    print(Fore.YELLOW + "\n=== Player Setup ===" + Style.RESET_ALL)

    master_logger = MasterLogger.get_instance()

    # Setup player data if not already written
    if not any(p.code_name == ps.code_name for p in gs.players):
        master_logger.log("Starting Setup screen...")
        ps.written_to_file = True
        player_setup = PlayerSetup()
        ps, gs, ps = player_setup.run(gs)
        gs.players.append(ps)
        gs.players.append(ps.ai_doppleganger.player_state)

        # Save both the player and their doppelganger to the lobby file
        save_player_to_lobby_file(ps)
        save_player_to_lobby_file(ps.ai_doppleganger.player_state)

    # Synchronize the player list once all players are ready
    print_str = ''
    while len([p for p in gs.players if p.is_human]) < gs.number_of_human_players:
        sleep(1)
        # Load the players from the lobby once all players are set up
        gs.players = load_players_from_lobby(gs)
        human_players = [p for p in gs.players if p.is_human]
        new_str = f"{len(human_players)}/{gs.number_of_human_players} players are ready."
        if print_str != new_str:
            print(new_str)
            print_str = new_str
            
    # Ensure consistent player list before continuing
    print(Fore.GREEN + "All players are ready!" + Style.RESET_ALL)
    input(Fore.MAGENTA + "Press Enter to continue to the chat phase..." + Style.RESET_ALL)
    synchronize_start_time(gs, ps)
    ps.ai_doppleganger.initialize_game_state(gs)
    gs.players = load_players_from_lobby(gs)
    gs.players = sorted(gs.players, key=lambda p: p.code_name)

    # Cut the deck of icebreakers based on the lobby ID
    icebreakers = gs.icebreakers  # assuming this is a list
    first_breaker = [icebreakers[0]]
    the_rest = icebreakers[1:]

    # Use modulo to rotate based on lobby_id
    start_idx = int(ps.lobby_id) % len(the_rest)
    first_chunk = the_rest[start_idx:]
    second_chunk = the_rest[:start_idx]

    # Final reordered list
    final_icebreakers = first_breaker + first_chunk + second_chunk
    gs.icebreakers = final_icebreakers

    return ScreenEnum.CHAT, gs, ps
