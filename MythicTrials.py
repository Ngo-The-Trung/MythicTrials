import collections
import ctypes
import inspect
import os
import sys
import random

# Add the base directory to sys.path for testing- allows us to run the mod
# directly for quick testing
sys.path.append('../..')


import CommonContent
import Consumables
# import Game
import Level
# import Monsters
import Mutators


def get_RiftWizard():
    # Returns the RiftWizard.py module object
    for f in inspect.stack()[::-1]:
        if "file 'RiftWizard.py'" in str(f):
            break

    return f


def get_cur_game():
    # Returns the current Game object
    RiftWizard = get_RiftWizard()

    return RiftWizard.frame.f_locals["main_view"].game


##### Spells/Items
class SpellWhiskey(Level.Spell):

    def on_init(self):
        self.range = 0

    def cast_instant(self, x, y):
        num_damage_spells, num_other_spells, num_upgrades = (
            self.unlearn_all_spells()
        )
        self.learn_random_spells(
            num_damage_spells, num_other_spells, num_upgrades
        )

    def unlearn_all_spells(self):
        # Returns numbers of damage spells, other spells and upgrades
        num_damage_spells = len([
            sp for sp in self.caster.spells if self.is_damage_spell(sp)
        ])
        num_other_spells = len([
            sp for sp in self.caster.spells if not self.is_damage_spell(sp)
        ])
        num_upgrades = sum([
            1
            for spell in self.caster.spells for upgrade in spell.spell_upgrades
            if upgrade.applied
        ])

        # Nuke your spells and skills
        while len(self.caster.spells) > 0:
            self.caster.remove_spell(self.caster.spells[-1])

        return num_damage_spells, num_other_spells, num_upgrades

    def count_distinct_upgrades(self, spell):
        # Count upgrades, treating exclusive upgrade groups as 1 each
        total = 0
        seen = set()
        for upgrade in spell.spell_upgrades:
            if not upgrade.exc_class:
                total += 1

            if upgrade.exc_class in seen:
                continue

            seen.add(upgrade.exc_class)
            total += 1

        return total

    def get_upgrade_candidates(self, spells):
        # If a spell has an exclusive group, we pull out an upgrade randomly
        # from that group
        candidates = []
        for spell in spells:
            groups = collections.defaultdict(lambda: [])
            for upgrade in spell.spell_upgrades:
                if not upgrade.exc_class:
                    candidates.append(upgrade)
                    continue

                groups[upgrade.exc_class].append(upgrade)

            for name, upgrades in groups.items():
                candidates.append(random.choice(upgrades))

        return candidates

    def is_damage_spell(self, spell):
        return (
            Level.Tags.Sorcery in spell.tags or (
                Level.Tags.Conjuration in spell.tags
                and not(Level.Tags.Enchantment in spell.tags)
            )
        )

    def learn_random_spells(
        self, num_damage_spells, num_other_spells, num_upgrades
    ):
        """
        Relearn rules:
        1. Sorcery and non-enchantment conjuration spells are considered damage
           spells
        2. Damage spells are only replaced by damage spells
        3. The rest are completely random
        This is mostly to ensure that the player can do *some* damage after
        drinking, which should reduces the chance of softlocking
        It won't prevent you from dying, so drink responsibly
        """

        # Make a copy so we don't shuffle internal data
        all_spells = [sp for sp in get_cur_game().all_player_spells]
        all_damage_spells = [
            sp for sp in all_spells if self.is_damage_spell(sp)
        ]
        all_other_spells = [
            sp for sp in all_spells if not self.is_damage_spell(sp)
        ]
        # Reroll spells until they have enough rooms to fit our upgrades
        # I suppose it's probably possible to get so many upgrades that this
        # will reroll until you get exactly the same spells and upgrades
        # but it's not worth working around yet
        while True:
            random.shuffle(all_damage_spells)
            random.shuffle(all_other_spells)

            spell_candidates = (
                all_damage_spells[:num_damage_spells]
                + all_other_spells[:num_other_spells]
            )
            total_upgrades = sum([
                self.count_distinct_upgrades(spell)
                for spell in spell_candidates
            ])
            if total_upgrades < num_upgrades:
                # We'll lose upgrades if we proceed, reroll
                continue

            break

        learnable_upgrades = self.get_upgrade_candidates(spell_candidates)
        random.shuffle(learnable_upgrades)
        upgrade_candidates = learnable_upgrades[:num_upgrades]

        # Add spells + upgrades to players
        for spell in spell_candidates:
            self.caster.add_spell(spell)

        for upgrade in upgrade_candidates:
            self.caster.apply_buff(upgrade)


def whiskey():
    item = Level.Item()
    item.name = "Whiskey"
    item.description = ("Randomizes your spells and upgrades then recharge "
        "your spells")
    item.set_spell(SpellWhiskey())
    return item


##### Mutators


class AllEnemiesToD(Mutators.Mutator):
    def __init__(self):
        Mutators.Mutator.__init__(self)
        self.description = "All enemies learn Touch of Death"
        self.global_triggers[Level.EventOnUnitPreAdded] = self.on_unit_pre_added

    def on_unit_pre_added(self, evt):
        self.add_tod(evt.unit)

    def on_levelgen(self, levelgen):
        for unit in levelgen.level.units:
            self.add_tod(unit)

    def add_tod(self, unit):
        if unit.is_lair:
            return

        if unit.team == Level.TEAM_PLAYER:
            return

        # Remove base melee attack
        for i, spell in enumerate(unit.spells):
            if isinstance(spell, CommonContent.SimpleMeleeAttack):
                unit.spells.pop(i)
                break

        # Each unit needs its own spell instance btw
        tod = CommonContent.SimpleMeleeAttack(
            damage=200, damage_type=Level.Tags.Dark
        )
        tod.name = "Touch of Death"
        unit.spells.insert(0, tod)

        # From Level.py:3024
        # Wouldn't surprise me if future versions crashed due to this
        unit.spells[0].caster = unit
        unit.spells[0].owner = unit

        return unit


class AllConsumablesDeathDice(Mutators.Mutator):
    def __init__(self):
        Mutators.Mutator.__init__(self)
        self.description = ("A non health/mana potion consumables are replaced "
            "with Death Dice")

    def on_levelgen(self, levelgen):
        self.replace_consumables(levelgen.items)

    def replace_consumables(self, items):
        for i, item in enumerate(items):
            if item.name != "Healing Potion" and item.name != "Mana Potion":
                items[i] = Consumables.death_dice()


class MordredOnlyWeakness(Mutators.Mutator):
    def __init__(self):
        Mutators.Mutator.__init__(self)
        self.description = "Mordred can only be damaged through Death Dice"

        self.global_triggers[Level.EventOnPreDamaged] = self.on_pre_damaged

    def on_pre_damaged(self, evt):
        if evt.unit.name != "Mordred":
            return

        if isinstance(evt.source, Consumables.DeathDiceSpell):
            return

        # Reduces damage to 0
        for f in inspect.stack()[::-1]:
            if f.function != "deal_damage":
                continue

            frame = f.frame
            frame.f_locals.update({
                "amount": 0,
            })
            # clown world
            ctypes.pythonapi.PyFrame_LocalsToFast(
                ctypes.py_object(frame), ctypes.c_int(0)
            )


class DrunkenMage(Mutators.Mutator):
    def __init__(self):
        Mutators.Mutator.__init__(self)
        self.description = ("All mana potions are whiskeys which randomize "
            "your spells, upgrades and skills")

    def on_game_begin(self, game):
        game.p1.remove_item(Consumables.mana_potion())
        game.p1.add_item(whiskey())
        game.p1.add_item(whiskey())
        game.p1.add_item(whiskey())
        game.p1.add_item(whiskey())
        game.p1.add_item(whiskey())
        game.p1.add_item(whiskey())
        game.p1.add_item(whiskey())

    def on_levelgen(self, levelgen):
        items = levelgen.items
        for i, item in enumerate(items):
            if item.name == "Mana Potion":
                items[i] = whiskey()


##### Debugging/cheating

class BigCheat(Mutators.Mutator):
    def __init__(self):
        Mutators.Mutator.__init__(self)
        self.description = "Testing"
        self.global_triggers[Level.EventOnUnitPreAdded] = self.on_unit_pre_added

    def on_game_begin(self, game):
        game.p1.max_hp = 10000
        game.p1.cur_hp = 10000
        for tag in [
            Level.Tags.Dark,
            Level.Tags.Arcane,
            Level.Tags.Physical,
            Level.Tags.Fire,
            Level.Tags.Ice,
            Level.Tags.Lightning,
            Level.Tags.Poison,
        ]:
            game.p1.resists[tag] = 50
        game.p1.xp = 1000

        # Death dices
        for _ in range(50):
            game.p1.add_item(Consumables.death_dice())

    def on_unit_pre_added(self, evt):
        self.make_mordred_dumb(evt.unit)

    def on_levelgen(self, levelgen):
        for unit in levelgen.level.units:
            self.make_mordred_dumb(unit)

    def make_mordred_dumb(self, unit):
        if unit.name != "Mordred":
            return

        unit.spells = []

        return unit


def cheatify(mutator_list):
    if 'cheatmode' in sys.argv:
        return mutator_list + [BigCheat()]

    return mutator_list


##### End Debugging


Mutators.all_trials.append(
    Mutators.Trial("Danse Macabre", cheatify([
        AllEnemiesToD(),
        AllConsumablesDeathDice(),
        MordredOnlyWeakness(),
    ]))
)
Mutators.all_trials.append(
    Mutators.Trial("Drunken Mage", cheatify([
        DrunkenMage(),
    ]))
)


##### Patches
def patch_spell_icon():
    # Make spell icons loadable from mod folder
    RiftWizard = get_RiftWizard()
    frame = RiftWizard.frame
    PyGameView = frame.f_locals["PyGameView"]
    orig = PyGameView.draw_spell_icon

    def _impl_(self, spell, surface, x, y, grey=False, animated=False):
        icon = orig(self, spell, surface, x, y, grey, animated)

        if icon:
            return icon

        # Search in mods
        for mod in os.listdir('mods'):
            path = os.path.join('mods', mod)
            os.chdir(path)
            icon = orig(self, spell, surface, x, y, grey, animated)
            if icon:
                os.chdir(path)
                break
            os.chdir("../../")

        return icon

    PyGameView.draw_spell_icon = _impl_


patch_spell_icon()
