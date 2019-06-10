from bombman import *

class Player(Positionable):
    # possible player states
    STATE_IDLE_UP = 0
    STATE_IDLE_RIGHT = 1
    STATE_IDLE_DOWN = 2
    STATE_IDLE_LEFT = 3
    STATE_WALKING_UP = 4
    STATE_WALKING_RIGHT = 5
    STATE_WALKING_DOWN = 6
    STATE_WALKING_LEFT = 7
    STATE_IN_AIR = 8
    STATE_TELEPORTING = 9
    STATE_DEAD = 10

    DISEASE_NONE = 0
    DISEASE_DIARRHEA = 1
    DISEASE_SLOW = 2
    DISEASE_REVERSE_CONTROLS = 3
    DISEASE_SHORT_FLAME = 4
    DISEASE_SWITCH_PLAYERS = 5
    DISEASE_FAST_BOMB = 6
    DISEASE_NO_BOMB = 7
    DISEASE_EARTHQUAKE = 8

    INITIAL_SPEED = 3
    SLOW_SPEED = 1.5
    MAX_SPEED = 10
    SPEEDUP_VALUE = 1
    DISEASE_TIME = 20000

    JUMP_DURATION = 2000
    TELEPORT_DURATION = 1500

    # ----------------------------------------------------------------------------

    def __init__(self):
        super(Player, self).__init__()
        self.number = 0  ##< player's number
        self.team_number = 0  ##< team number, determines player's color
        self.state = Player.STATE_IDLE_DOWN
        self.state_time = 0  ##< how much time (in ms) has been spent in current state
        self.speed = Player.INITIAL_SPEED  ##< speed in tiles per second
        self.bombs_left = 1  ##< how many more bombs the player can put at the time
        self.flame_length = 1  ##< how long the flame is in tiles
        self.items = {}  ##< which items and how many the player has, format: [item code]: count
        self.has_spring = False  ##< whether player's bombs have springs
        self.has_shoe = False  ##< whether player has a kicking shoe
        self.disease_time_left = 0
        self.disease = Player.DISEASE_NONE
        self.has_multibomb = False
        self.has_boxing_glove = False
        self.has_throwing_glove = False
        self.boxing = False
        self.detonator_bombs_left = 0  ##< what number of following bombs will have detonators
        self.detonator_bombs = []  ##< references to bombs to be detonated
        self.wait_for_special_release = False  ##< helper used to wait for special key release
        self.wait_for_bomb_release = False
        self.throwing_time_left = 0  ##< for how longer (in ms) the player will be in a state of throwing (only for visuals)
        self.state_backup = Player.STATE_IDLE_UP  ##< used to restore previous state, for example after jump
        self.jumping_to = (0, 0)  ##< coordinates of a tile the player is jumping to
        self.teleporting_to = (0, 0)
        self.wait_for_tile_transition = False  ##< used to stop the destination teleport from teleporting the player back immediatelly
        self.invincible = False  ##< can be used to make the player immortal
        self.info_board_update_needed = True
        self.kills = 0
        self.wins = 0

        self.items[GameMap.ITEM_BOMB] = 1
        self.items[GameMap.ITEM_FLAME] = 1

    # ----------------------------------------------------------------------------

    def get_kills(self):
        return self.kills

    # ----------------------------------------------------------------------------

    def set_kills(self, kills):
        self.kills = kills
        self.info_board_update_needed = True

    # ----------------------------------------------------------------------------

    def get_wins(self):
        return self.wins

    # ----------------------------------------------------------------------------

    def set_wins(self, wins):
        self.wins = wins
        self.info_board_update_needed = True

    # ----------------------------------------------------------------------------

    def info_board_needs_update(self):
        if self.info_board_update_needed:
            self.info_board_update_needed = False
            return True

        return False

    # ----------------------------------------------------------------------------

    ## Makes the player not react to bomb key immediatelly, but only after it
    #  has been released and pressed again.

    def wait_for_bomb_action_release(self):
        self.wait_for_bomb_release = True

    # ----------------------------------------------------------------------------

    ## Makes the player not react to special key immediatelly, but only after it
    #  has been released and pressed again.

    def wait_for_special_action_release(self):
        self.wait_for_special_release = True

    # ----------------------------------------------------------------------------

    def is_walking(self):
        return self.state in [Player.STATE_WALKING_UP, Player.STATE_WALKING_RIGHT, Player.STATE_WALKING_DOWN,
                              Player.STATE_WALKING_LEFT]

    # ----------------------------------------------------------------------------

    def is_boxing(self):
        return self.boxing

    ## Checks if there are any bombs waiting to be detonated with detonator by
    #  the player.

    # ----------------------------------------------------------------------------

    def detonator_is_active(self):
        return len(self.detonator_bombs) > 0

    # ----------------------------------------------------------------------------

    def kill(self, game_map):
        if self.invincible:
            return

        self.info_board_update_needed = True

        self.state = Player.STATE_DEAD
        game_map.add_sound_event(SoundPlayer.SOUND_EVENT_DEATH)

        random_animation = random.choice((
            Renderer.ANIMATION_EVENT_DIE,
            Renderer.ANIMATION_EVENT_EXPLOSION,
            Renderer.ANIMATION_EVENT_RIP,
            Renderer.ANIMATION_EVENT_SKELETION))

        game_map.add_animation_event(random_animation, Renderer.map_position_to_pixel_position(self.position, (0, -15)))
        game_map.give_away_items(self.get_items())

    # ----------------------------------------------------------------------------

    def is_enemy(self, another_player):
        return self.team_number != another_player.get_team_number()

    # ----------------------------------------------------------------------------

    ## Returns a number that says which way the player is facing (0 - up, 1 - right,
    #  2 - down, 3 - left).

    def get_direction_number(self):
        if self.state in [Player.STATE_IDLE_UP, Player.STATE_WALKING_UP]:
            return 0
        elif self.state in [Player.STATE_IDLE_RIGHT, Player.STATE_WALKING_RIGHT]:
            return 1
        elif self.state in [Player.STATE_IDLE_DOWN, Player.STATE_WALKING_DOWN]:
            return 2
        else:
            return 3

    # ----------------------------------------------------------------------------

    def is_dead(self):
        return self.state == Player.STATE_DEAD

    # ----------------------------------------------------------------------------

    ## Returns a number of bomb the player can currently lay with multibomb (if
    #   the player doesn't have multibomb, either 1 or 0 will be returned).

    def get_multibomb_count(self):
        if not self.has_multibomb:
            return 1 if self.bombs_left > 0 else 0

        return self.bombs_left

    # ----------------------------------------------------------------------------

    ## Initialises the teleporting of the player with teleport they are standing on (if they're
    #   not standing on a teleport, nothing happens).

    def teleport(self, game_map):
        if self.wait_for_tile_transition:
            return

        current_tile = self.get_tile_position()
        destination_coordinates = game_map.get_tile_at(current_tile).destination_teleport

        if destination_coordinates == None:
            return

        game_map.add_sound_event(SoundPlayer.SOUND_EVENT_TELEPORT)

        self.move_to_tile_center()
        self.teleporting_to = destination_coordinates

        self.state_backup = self.state
        self.state = Player.STATE_TELEPORTING
        self.state_time = 0
        self.wait_for_tile_transition = True

    # ----------------------------------------------------------------------------

    def get_items(self):
        result = []

        for item in self.items:
            result += [item for i in xrange(self.items[item])]

        return result

    # ----------------------------------------------------------------------------

    def send_to_air(self, game_map):
        if self.state == Player.STATE_IN_AIR:
            return

        game_map.add_sound_event(SoundPlayer.SOUND_EVENT_TRAMPOLINE)

        self.state_backup = self.state
        self.state = Player.STATE_IN_AIR
        self.jumping_from = self.get_tile_position()

        landing_tiles = []  # potential tiles to land on

        # find a landing tile

        for y in range(self.jumping_from[1] - 3, self.jumping_from[1] + 4):
            for x in range(self.jumping_from[0] - 3, self.jumping_from[0] + 4):
                tile = game_map.get_tile_at((x, y))

                if tile != None and game_map.tile_is_walkable((x, y)) and tile.special_object == None:
                    landing_tiles.append((x, y))

        if len(landing_tiles) == 0:  # this should practically not happen
            self.jumping_to = (self.jumping_from[0], self.jumping_from[1] + 1)
        else:
            self.jumping_to = random.choice(landing_tiles)

        self.state_time = 0

    # ----------------------------------------------------------------------------

    def get_state_time(self):
        return self.state_time

    # ----------------------------------------------------------------------------

    def get_teleport_destination(self):
        return self.teleporting_to

    # ----------------------------------------------------------------------------

    def get_jump_destination(self):
        return self.jumping_to

    # ----------------------------------------------------------------------------

    def is_teleporting(self):
        return self.state == Player.STATE_TELEPORTING

    # ----------------------------------------------------------------------------

    def is_in_air(self):
        return self.state == Player.STATE_IN_AIR

    # ----------------------------------------------------------------------------

    def is_throwing(self):
        return self.throwing_time_left > 0

    # ----------------------------------------------------------------------------

    def can_box(self):
        return self.has_boxing_glove

    # ----------------------------------------------------------------------------

    def can_throw(self):
        return self.has_throwing_glove

    # ----------------------------------------------------------------------------

    def get_item_count(self, item):
        if not item in self.items:
            return 0

        return self.items[item]

    # ----------------------------------------------------------------------------

    ## Gives player an item with given code (see GameMap class constants). game_map
    #  is needed so that sounds can be made on item pickup - if no map is provided,
    #  no sounds will be generated.

    def give_item(self, item, game_map=None):
        self.items[item] = 1 if not item in self.items else self.items[item] + 1

        self.info_board_update_needed = True

        if item == GameMap.ITEM_RANDOM:
            item = random.choice((
                GameMap.ITEM_BOMB,
                GameMap.ITEM_FLAME,
                GameMap.ITEM_SUPERFLAME,
                GameMap.ITEM_MULTIBOMB,
                GameMap.ITEM_SPRING,
                GameMap.ITEM_SHOE,
                GameMap.ITEM_SPEEDUP,
                GameMap.ITEM_DISEASE,
                GameMap.ITEM_BOXING_GLOVE,
                GameMap.ITEM_DETONATOR,
                GameMap.ITEM_THROWING_GLOVE
            ))

        sound_to_make = SoundPlayer.SOUND_EVENT_CLICK

        if item == GameMap.ITEM_BOMB:
            self.bombs_left += 1
        elif item == GameMap.ITEM_FLAME:
            self.flame_length += 1
        elif item == GameMap.ITEM_SUPERFLAME:
            self.flame_length = max(GameMap.MAP_WIDTH, GameMap.MAP_HEIGHT)
        elif item == GameMap.ITEM_MULTIBOMB:
            self.has_multibomb = True
        elif item == GameMap.ITEM_DETONATOR:
            self.detonator_bombs_left = 3
        elif item == GameMap.ITEM_SPRING:
            self.has_spring = True
            sound_to_make = SoundPlayer.SOUND_EVENT_SPRING
        elif item == GameMap.ITEM_SPEEDUP:
            self.speed = min(self.speed + Player.SPEEDUP_VALUE, Player.MAX_SPEED)
        elif item == GameMap.ITEM_SHOE:
            self.has_shoe = True
        elif item == GameMap.ITEM_BOXING_GLOVE:
            self.has_boxing_glove = True
        elif item == GameMap.ITEM_THROWING_GLOVE:
            self.has_throwing_glove = True
        elif item == GameMap.ITEM_DISEASE:
            chosen_disease = random.choice([
                (Player.DISEASE_SHORT_FLAME, SoundPlayer.SOUND_EVENT_DISEASE),
                (Player.DISEASE_SLOW, SoundPlayer.SOUND_EVENT_SLOW),
                (Player.DISEASE_DIARRHEA, SoundPlayer.SOUND_EVENT_DIARRHEA),
                (Player.DISEASE_FAST_BOMB, SoundPlayer.SOUND_EVENT_DISEASE),
                (Player.DISEASE_REVERSE_CONTROLS, SoundPlayer.SOUND_EVENT_DISEASE),
                (Player.DISEASE_SWITCH_PLAYERS, SoundPlayer.SOUND_EVENT_DISEASE),
                (Player.DISEASE_NO_BOMB, SoundPlayer.SOUND_EVENT_DISEASE),
                (Player.DISEASE_EARTHQUAKE, SoundPlayer.SOUND_EVENT_EARTHQUAKE)
            ])

            if chosen_disease[0] == Player.DISEASE_SWITCH_PLAYERS:
                if game_map != None:
                    players = filter(lambda p: not p.is_dead(), game_map.get_players())

                    player_to_switch = self

                    if len(players) > 1:  # should always be true
                        while player_to_switch == self:
                            player_to_switch = random.choice(players)

                    my_position = self.get_position()
                    self.set_position(player_to_switch.get_position())
                    player_to_switch.set_position(my_position)
            elif chosen_disease[0] == Player.DISEASE_EARTHQUAKE:
                if game_map != None:
                    game_map.start_earthquake()
            else:
                self.disease = chosen_disease[0]
                self.disease_time_left = Player.DISEASE_TIME

            sound_to_make = chosen_disease[1]

        if game_map != None and sound_to_make != None:
            game_map.add_sound_event(sound_to_make)

    # ----------------------------------------------------------------------------

    def lay_bomb(self, game_map, tile_coordinates=None):
        new_bomb = Bomb(self)

        if tile_coordinates != None:
            new_bomb.set_position(tile_coordinates)
            new_bomb.move_to_tile_center()

        game_map.add_bomb(new_bomb)
        game_map.add_sound_event(SoundPlayer.SOUND_EVENT_BOMB_PUT)
        self.bombs_left -= 1

        if self.disease == Player.DISEASE_SHORT_FLAME:
            new_bomb.flame_length = 1
        elif self.disease == Player.DISEASE_FAST_BOMB:
            new_bomb.explodes_in = Bomb.EXPLODES_IN_QUICK

        if self.detonator_bombs_left > 0:
            new_bomb.detonator_time = Bomb.DETONATOR_EXPIRATION_TIME
            self.detonator_bombs.append(new_bomb)
            self.detonator_bombs_left -= 1

    # ----------------------------------------------------------------------------

    def get_bombs_left(self):
        return self.bombs_left

    # ----------------------------------------------------------------------------

    def get_disease(self):
        return self.disease

    # ----------------------------------------------------------------------------

    def get_disease_time(self):
        return self.disease_time_left

    # ----------------------------------------------------------------------------

    def set_disease(self, disease, time_left):
        self.disease = disease
        self.disease_time_left = time_left

    # ----------------------------------------------------------------------------

    def bombs_have_spring(self):
        return self.has_spring

    # ----------------------------------------------------------------------------

    def set_number(self, number):
        self.number = number

    # ----------------------------------------------------------------------------

    def set_team_number(self, number):
        self.team_number = number

    # ----------------------------------------------------------------------------

    ## Must be called when this player's bomb explodes so that their bomb limit is increased again.

    def bomb_exploded(self):
        self.bombs_left += 1

    # ----------------------------------------------------------------------------

    def get_number(self):
        return self.number

    # ----------------------------------------------------------------------------

    def get_team_number(self):
        return self.team_number

    # ----------------------------------------------------------------------------

    def get_state(self):
        return self.state

    # ----------------------------------------------------------------------------

    def get_state_time(self):
        return self.state_time

    # ----------------------------------------------------------------------------

    def get_flame_length(self):
        return self.flame_length

    # ----------------------------------------------------------------------------

    ## Gets a direction vector (x and y: 0, 1 or -1) depending on where the player is facing.

    def get_direction_vector(self):
        if self.state in [Player.STATE_WALKING_UP, Player.STATE_IDLE_UP]:
            return (0, -1)
        elif self.state in [Player.STATE_WALKING_RIGHT, Player.STATE_IDLE_RIGHT]:
            return (1, 0)
        elif self.state in [Player.STATE_WALKING_DOWN, Player.STATE_IDLE_DOWN]:
            return (0, 1)
        else:  # left
            return (-1, 0)

    # ----------------------------------------------------------------------------

    def get_forward_tile_position(self):
        direction_vector = self.get_direction_vector()
        position = self.get_tile_position()
        return (position[0] + direction_vector[0], position[1] + direction_vector[1])

    # ----------------------------------------------------------------------------

    def __manage_input_actions(self, input_actions, game_map, distance_to_travel):
        moved = False  # to allow movement along only one axis at a time
        detonator_triggered = False
        special_was_pressed = False
        bomb_was_pressed = False

        for item in input_actions:
            if item[0] != self.number:
                continue  # not an action for this player

            input_action = item[1]

            if self.disease == Player.DISEASE_REVERSE_CONTROLS:
                input_action = PlayerKeyMaps.get_opposite_action(input_action)

            if not moved:
                if input_action == PlayerKeyMaps.ACTION_UP:
                    self.position[1] -= distance_to_travel
                    self.state = Player.STATE_WALKING_UP
                    moved = True
                elif input_action == PlayerKeyMaps.ACTION_DOWN:
                    self.position[1] += distance_to_travel
                    self.state = Player.STATE_WALKING_DOWN
                    moved = True
                elif input_action == PlayerKeyMaps.ACTION_RIGHT:
                    self.position[0] += distance_to_travel
                    self.state = Player.STATE_WALKING_RIGHT
                    moved = True
                elif input_action == PlayerKeyMaps.ACTION_LEFT:
                    self.position[0] -= distance_to_travel
                    self.state = Player.STATE_WALKING_LEFT
                    moved = True

            if input_action == PlayerKeyMaps.ACTION_BOMB:
                bomb_was_pressed = True

                if not self.wait_for_bomb_release and self.bombs_left >= 1 and not game_map.tile_has_bomb(
                        self.position) and not self.disease == Player.DISEASE_NO_BOMB:
                    self.putting_bomb = True

            if input_action == PlayerKeyMaps.ACTION_BOMB_DOUBLE:  # check multibomb
                if self.has_throwing_glove:
                    self.throwing = True
                elif self.has_multibomb:
                    self.putting_multibomb = True

            if input_action == PlayerKeyMaps.ACTION_SPECIAL:
                special_was_pressed = True

                if not self.wait_for_special_release:
                    while len(
                            self.detonator_bombs) != 0:  # find a bomb to ddetonate (some may have exploded by themselves already)
                        self.info_board_update_needed = True

                        bomb_to_check = self.detonator_bombs.pop()

                        if bomb_to_check.has_detonator() and not bomb_to_check.has_exploded and bomb_to_check.movement != Bomb.BOMB_FLYING:
                            game_map.bomb_explodes(bomb_to_check)
                            detonator_triggered = True
                            self.wait_for_special_release = True  # to not detonate other bombs until the key is released and pressed again
                            break

                    if not detonator_triggered and self.has_boxing_glove:
                        self.boxing = True

        if moved:
            game_map.add_sound_event(SoundPlayer.SOUND_EVENT_WALK)

        if not special_was_pressed:
            self.wait_for_special_release = False

        if not bomb_was_pressed:
            self.wait_for_bomb_release = False

    # ----------------------------------------------------------------------------

    def __manage_kick_box(self, game_map, collision_happened):
        if collision_happened:
            bomb_movement = Bomb.BOMB_NO_MOVEMENT

            bomb_movement = {
                Player.STATE_WALKING_UP: Bomb.BOMB_ROLLING_UP,
                Player.STATE_WALKING_RIGHT: Bomb.BOMB_ROLLING_RIGHT,
                Player.STATE_WALKING_DOWN: Bomb.BOMB_ROLLING_DOWN,
                Player.STATE_WALKING_LEFT: Bomb.BOMB_ROLLING_LEFT
            }[self.state]

            direction_vector = self.get_direction_vector()
            forward_tile = self.get_forward_tile_position()

            if (self.has_shoe or self.has_boxing_glove) and game_map.tile_has_bomb(forward_tile):
                # kick or box happens
                bomb_hit = game_map.bomb_on_tile(forward_tile)

                if self.boxing:
                    destination_tile = (
                    forward_tile[0] + direction_vector[0] * 3, forward_tile[1] + direction_vector[1] * 3)
                    bomb_hit.send_flying(destination_tile)
                    game_map.add_sound_event(SoundPlayer.SOUND_EVENT_KICK)
                elif self.has_shoe:
                    # align the bomb in case of kicking an already moving bomb
                    bomb_position = bomb_hit.get_position()

                    if bomb_movement == Bomb.BOMB_ROLLING_LEFT or bomb_movement == Bomb.BOMB_ROLLING_RIGHT:
                        bomb_hit.set_position((bomb_position[0], math.floor(bomb_position[1]) + 0.5))
                    else:
                        bomb_hit.set_position((math.floor(bomb_position[0]) + 0.5, bomb_position[1]))

                    bomb_hit.movement = bomb_movement
                    game_map.add_sound_event(SoundPlayer.SOUND_EVENT_KICK)

    # ----------------------------------------------------------------------------

    def __resolve_collisions(self, game_map, distance_to_travel, previous_position):
        collision_type = game_map.get_position_collision_type(self.position)
        collision_happened = False

        if collision_type == GameMap.COLLISION_TOTAL:
            self.position = previous_position
            collision_happened = True
        else:
            helper_mapping = {
                GameMap.COLLISION_BORDER_UP: (
                Player.STATE_WALKING_UP, [Player.STATE_WALKING_LEFT, Player.STATE_WALKING_RIGHT],
                (0, distance_to_travel)),
                GameMap.COLLISION_BORDER_DOWN: (
                Player.STATE_WALKING_DOWN, [Player.STATE_WALKING_LEFT, Player.STATE_WALKING_RIGHT],
                (0, -1 * distance_to_travel)),
                GameMap.COLLISION_BORDER_RIGHT: (
                Player.STATE_WALKING_RIGHT, [Player.STATE_WALKING_UP, Player.STATE_WALKING_DOWN],
                (- 1 * distance_to_travel, 0)),
                GameMap.COLLISION_BORDER_LEFT: (
                Player.STATE_WALKING_LEFT, [Player.STATE_WALKING_UP, Player.STATE_WALKING_DOWN],
                (distance_to_travel, 0))
            }

            if collision_type in helper_mapping:
                helper_values = helper_mapping[collision_type]

                if self.state == helper_values[0]:  # walking against the border won't allow player to pass
                    self.position = previous_position
                    collision_happened = True
                elif self.state in helper_values[1]:  # walking along the border will shift the player sideways
                    self.position[0] += helper_values[2][0]
                    self.position[1] += helper_values[2][1]

        return collision_happened

    # ----------------------------------------------------------------------------

    ## Sets the state and other attributes like position etc. of this player accoording to a list of input action (returned by PlayerKeyMaps.get_current_actions()).

    def react_to_inputs(self, input_actions, dt, game_map):
        if self.state == Player.STATE_DEAD or game_map.get_state() == GameMap.STATE_WAITING_TO_PLAY:
            return

        if self.state in [Player.STATE_IN_AIR, Player.STATE_TELEPORTING]:
            self.state_time += dt

            if self.state_time >= (
            Player.JUMP_DURATION if self.state == Player.STATE_IN_AIR else Player.TELEPORT_DURATION):
                self.state = self.state_backup
                self.state_time = 0
                self.jumping_to = None
                self.teleporting_to = None
            else:
                return

        current_speed = self.speed if self.disease != Player.DISEASE_SLOW else Player.SLOW_SPEED

        distance_to_travel = dt / 1000.0 * current_speed

        self.throwing_time_left = max(0, self.throwing_time_left - dt)

        self.position = list(self.position)  # in case position was tuple

        old_state = self.state

        if self.state in (Player.STATE_WALKING_UP, Player.STATE_IDLE_UP):
            self.state = Player.STATE_IDLE_UP
        elif self.state in (Player.STATE_WALKING_RIGHT, Player.STATE_IDLE_RIGHT):
            self.state = Player.STATE_IDLE_RIGHT
        elif self.state in (Player.STATE_WALKING_DOWN, Player.STATE_IDLE_DOWN):
            self.state = Player.STATE_IDLE_DOWN
        else:
            self.state = Player.STATE_IDLE_LEFT

        previous_position = copy.copy(self.position)  # in case of collision we save the previous position

        self.putting_bomb = False
        self.putting_multibomb = False
        self.throwing = False
        self.boxing = False

        if self.disease == Player.DISEASE_DIARRHEA:
            input_actions.append((self.number, PlayerKeyMaps.ACTION_BOMB))  # inject bomb put event

        self.__manage_input_actions(input_actions, game_map, distance_to_travel)

        # resolve collisions:
        check_collisions = True

        current_tile = self.get_tile_position()
        previous_tile = Positionable.position_to_tile(previous_position)
        transitioning_tiles = current_tile != previous_tile

        if transitioning_tiles:
            self.wait_for_tile_transition = False

        if game_map.tile_has_bomb(current_tile):  # first check if the player is standing on a bomb
            if not transitioning_tiles:
                check_collisions = False  # no transition between tiles -> let the player move

        collision_happened = False

        if check_collisions:
            collision_happened = self.__resolve_collisions(game_map, distance_to_travel, previous_position)

        if self.putting_bomb and not game_map.tile_has_bomb(
                self.get_tile_position()) and not game_map.tile_has_teleport(self.position):
            self.lay_bomb(game_map)

        # check if bomb kick or box happens
        self.__manage_kick_box(game_map, collision_happened)

        if self.throwing:
            bomb_thrown = game_map.bomb_on_tile(current_tile)
            game_map.add_sound_event(SoundPlayer.SOUND_EVENT_THROW)

            if bomb_thrown != None:
                forward_tile = self.get_forward_tile_position()
                direction_vector = self.get_direction_vector()
                destination_tile = (
                forward_tile[0] + direction_vector[0] * 3, forward_tile[1] + direction_vector[1] * 3)
                bomb_thrown.send_flying(destination_tile)
                self.wait_for_bomb_release = True
                self.throwing_time_left = 200

        elif self.putting_multibomb:  # put multibomb
            current_tile = self.get_tile_position()

            if self.state in (Player.STATE_WALKING_UP, Player.STATE_IDLE_UP):
                tile_increment = (0, -1)
            elif self.state in (Player.STATE_WALKING_RIGHT, Player.STATE_IDLE_RIGHT):
                tile_increment = (1, 0)
            elif self.state in (Player.STATE_WALKING_DOWN, Player.STATE_IDLE_DOWN):
                tile_increment = (0, 1)
            else:  # left
                tile_increment = (-1, 0)

            i = 1

            while self.bombs_left > 0:
                next_tile = (current_tile[0] + i * tile_increment[0], current_tile[1] + i * tile_increment[1])
                if not game_map.tile_is_walkable(next_tile) or game_map.tile_has_player(next_tile):
                    break

                self.lay_bomb(game_map, next_tile)
                i += 1

        # check disease

        if self.disease != Player.DISEASE_NONE:
            self.disease_time_left = max(0, self.disease_time_left - dt)

            if self.disease_time_left == 0:
                self.disease = Player.DISEASE_NONE
                self.info_board_update_needed = True

        if old_state == self.state:
            self.state_time += dt
        else:
            self.state_time = 0  # reset the state time
