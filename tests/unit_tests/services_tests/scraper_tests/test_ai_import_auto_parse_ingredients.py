from uuid import uuid4

import pytest

from mealie.lang.providers import get_locale_provider
from mealie.schema.recipe.recipe import Recipe
from mealie.schema.recipe.recipe_ingredient import (
    CreateIngredientFood,
    CreateIngredientUnit,
    IngredientFood,
    IngredientUnit,
    ParsedIngredient,
    RecipeIngredient,
    RegisteredParser,
)
from mealie.schema.recipe.recipe_step import RecipeStep
from mealie.services.scraper import recipe_scraper as recipe_scraper_module
from mealie.services.scraper.recipe_scraper import RecipeScraper
from mealie.services.scraper.scraped_extras import ScrapedExtras
from mealie.services.scraper.scraper_strategies import RecipeScraperOpenAI


class FakeRepos:
    group_id = "test-group"
    session = object()


class FakeParser:
    def __init__(self, ingredients: list[RecipeIngredient] | None = None, error: Exception | None = None):
        self.ingredients = ingredients or []
        self.error = error

    async def parse(self, ingredients: list[str]) -> list[ParsedIngredient]:
        if self.error:
            raise self.error

        return [
            ParsedIngredient(input=input_text, ingredient=ingredient)
            for input_text, ingredient in zip(ingredients, self.ingredients, strict=True)
        ]


class ImportedAIScraper(RecipeScraperOpenAI):
    def can_scrape(self) -> bool:
        return True

    async def parse(self, on_progress=None):
        return (
            Recipe(
                name="Pasta alla Trapanese",
                recipe_ingredient=[
                    RecipeIngredient(note="200 g geroestete Mandeln"),
                    RecipeIngredient(note="4 Knoblauchzehen"),
                ],
                recipe_instructions=[RecipeStep(text="Alles mixen.")],
            ),
            ScrapedExtras(),
        )


def ingredient(quantity: float, unit: str | None, food: str) -> RecipeIngredient:
    return RecipeIngredient(
        quantity=quantity,
        unit=IngredientUnit(id=uuid4(), name=unit) if unit else None,
        food=IngredientFood(id=uuid4(), name=food),
    )


def unmatched_ingredient(quantity: float, unit: str | None, food: str) -> RecipeIngredient:
    return RecipeIngredient(
        quantity=quantity,
        unit=CreateIngredientUnit(name=unit) if unit else None,
        food=CreateIngredientFood(name=food),
    )


@pytest.mark.asyncio
async def test_ai_import_auto_parses_ingredients_with_openai(monkeypatch: pytest.MonkeyPatch):
    def fake_get_parser(parser_type, group_id, session, translator):
        assert parser_type == RegisteredParser.openai
        return FakeParser(
            [
                ingredient(200, "g", "Mandeln"),
                ingredient(4, None, "Knoblauchzehen"),
            ]
        )

    monkeypatch.setattr(recipe_scraper_module, "get_parser", fake_get_parser)

    recipe, _ = await RecipeScraper(FakeRepos(), get_locale_provider(), [ImportedAIScraper]).scrape(
        "https://www.instagram.com/reel/test/", "<html></html>"
    )

    assert recipe.recipe_ingredient[0].quantity == 200
    assert recipe.recipe_ingredient[0].unit.name == "g"
    assert recipe.recipe_ingredient[0].food.name == "Mandeln"
    assert recipe.recipe_ingredient[1].quantity == 4
    assert recipe.recipe_ingredient[1].food.name == "Knoblauchzehen"


@pytest.mark.asyncio
async def test_ai_import_auto_parse_falls_back_to_nlp(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_get_parser(parser_type, group_id, session, translator):
        calls.append(parser_type)
        if parser_type == RegisteredParser.openai:
            return FakeParser(error=RuntimeError("openai unavailable"))
        return FakeParser(
            [
                ingredient(200, "g", "Mandeln"),
                ingredient(4, None, "Knoblauchzehen"),
            ]
        )

    monkeypatch.setattr(recipe_scraper_module, "get_parser", fake_get_parser)

    recipe, _ = await RecipeScraper(FakeRepos(), get_locale_provider(), [ImportedAIScraper]).scrape(
        "https://www.instagram.com/reel/test/", "<html></html>"
    )

    assert calls == [RegisteredParser.openai, RegisteredParser.nlp]
    assert recipe.recipe_ingredient[0].food.name == "Mandeln"
    assert recipe.recipe_ingredient[1].food.name == "Knoblauchzehen"


@pytest.mark.asyncio
async def test_ai_import_keeps_original_ingredients_when_parsers_fail(monkeypatch: pytest.MonkeyPatch):
    def fake_get_parser(parser_type, group_id, session, translator):
        return FakeParser(error=RuntimeError(f"{parser_type} unavailable"))

    monkeypatch.setattr(recipe_scraper_module, "get_parser", fake_get_parser)

    recipe, _ = await RecipeScraper(FakeRepos(), get_locale_provider(), [ImportedAIScraper]).scrape(
        "https://www.instagram.com/reel/test/", "<html></html>"
    )

    assert [ingredient.note for ingredient in recipe.recipe_ingredient] == [
        "200 g geroestete Mandeln",
        "4 Knoblauchzehen",
    ]


@pytest.mark.asyncio
async def test_ai_import_keeps_original_ingredients_when_food_is_unmatched(monkeypatch: pytest.MonkeyPatch):
    def fake_get_parser(parser_type, group_id, session, translator):
        return FakeParser(
            [
                unmatched_ingredient(200, "g", "Mandeln"),
                unmatched_ingredient(4, None, "Knoblauchzehen"),
            ]
        )

    monkeypatch.setattr(recipe_scraper_module, "get_parser", fake_get_parser)

    recipe, _ = await RecipeScraper(FakeRepos(), get_locale_provider(), [ImportedAIScraper]).scrape(
        "https://www.instagram.com/reel/test/", "<html></html>"
    )

    assert [ingredient.note for ingredient in recipe.recipe_ingredient] == [
        "200 g geroestete Mandeln",
        "4 Knoblauchzehen",
    ]
