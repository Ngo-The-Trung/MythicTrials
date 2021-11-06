import ctypes
import inspect
import os
import sys

# Add the base directory to sys.path for testing- allows us to run the mod
# directly for quick testing
sys.path.append('../..')


import CommonContent
import Consumables
# import Game
import Level
# import Monsters
import Mutators


##### Spells/Items
class SpellWhiskey(Level.Spell):

    def on_init(self):
        self.range = 0

        def cast_instant(self, x, y):
            for spell in self.caster.spells:
                spell.cur_charges = spell.get_stat('max_charges')


def whiskey():
    item = Level.Item()
    item.name = "Whiskey"
    # duration = 3
    item.description = ("Randomizes your spells, upgrades and skills then "
        "recharge your spells")
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
        items = game.p1.items
        for i in range(len(items) - 1, -1, -1):
            item = items[i]
            if item.name == "Mana Potion":
                items[i] = whiskey()

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
    # Don't move this function around.
    # RiftWizard calls this module so we can't import RiftWizard directly
    frame = inspect.stack()[-1].frame
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
