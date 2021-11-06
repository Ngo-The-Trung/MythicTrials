# Add the base directory to sys.path for testing- allows us to run the mod directly for quick testing
import sys
sys.path.append('../..')

import CommonContent
import Consumables
import Level
import Monsters
import Spells
import Game


def add_tod_factory(unit_factory):
    def unit_with_tod():
        # Add touch of death to unit
        unit = unit_factory()
        tod = CommonContent.SimpleMeleeAttack(damage=200, damage_type=Level.Tags.Dark)
        tod.name = "Touch of Death"

        # TODO remove regular attacks, cleaner this way
        unit.spells.insert(0, tod)  # preferred to regular attacks

        return unit

    return unit_with_tod


def add_tod_all_units():
    for i, (unit, level) in enumerate(Monsters.spawn_options):
        Monsters.spawn_options[i] = (add_tod_factory(unit), level)


def only_death_dice():
    Consumables.all_consumables = [
        (Consumables.death_dice, Consumables.COMMON)
    ]


def mordred_only_weakness():
    # Make Mordred take 0 damage from any spell that's not Death Dice
    orig_deal_damage = Level.Level.deal_damage

    def deal_damage(self, x, y, amount, damage_type, source, flash=True):
        unit = self.get_unit_at(x, y)
        if isinstance(unit, Monsters.Mordred):
            print("[MOD] Attempting to hurt Mordred with %s" % (source))
        return orig_deal_damage(self, x, y, amount, damage_type, source, flash=flash)

    Level.Level.deal_damage = deal_damage


add_tod_all_units()
only_death_dice()
mordred_only_weakness()


def test():
    def make_test_character():
        orig_make_player_character = Game.Game.make_player_character
        def make_invincible_char(self):
            player = orig_make_player_character(self)
            player.max_hp = 500
            player.cur_hp = 500
            for tag in [Level.Tags.Dark, Level.Tags.Physical, Level.Tags.Fire, Level.Tags.Ice, Level.Tags.Lightning]:
                player.resists[tag] = 200

            for _ in range(20):
                player.add_item(Consumables.death_dice())

            return player

        # Make something invincible
        Game.Game.make_player_character = make_invincible_char

    def spawn_mordred():
        Monsters.spawn_options = [
            (Monsters.Goblin, 1),
            (Monsters.Mordred, 1),
        ]

    make_test_character()
    spawn_mordred()


test()
