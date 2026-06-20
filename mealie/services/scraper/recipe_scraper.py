from collections.abc import Awaitable, Callable

from mealie.core.root_logger import get_logger
from mealie.lang.providers import Translator
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.recipe.recipe import Recipe
from mealie.schema.recipe.recipe_ingredient import RecipeIngredient, RegisteredParser
from mealie.services.parser_services import get_parser
from mealie.services.scraper import cleaner
from mealie.services.scraper.scraped_extras import ScrapedExtras

from .scraper_strategies import (
    ABCScraperStrategy,
    RecipeScraperOpenAI,
    RecipeScraperOpenAITranscription,
    RecipeScraperOpenGraph,
    RecipeScraperPackage,
    safe_scrape_html,
)

DEFAULT_SCRAPER_STRATEGIES: list[type[ABCScraperStrategy]] = [
    RecipeScraperPackage,
    RecipeScraperOpenAITranscription,
    RecipeScraperOpenAI,
    RecipeScraperOpenGraph,
]


class RecipeScraper:
    """
    Scrapes recipes from the web.
    """

    # List of recipe scrapers. Note that order matters
    scrapers: list[type[ABCScraperStrategy]]

    def __init__(
        self, repos: AllRepositories, translator: Translator, scrapers: list[type[ABCScraperStrategy]] | None = None
    ) -> None:
        if scrapers is None:
            scrapers = DEFAULT_SCRAPER_STRATEGIES

        self.scrapers = scrapers
        self.repos = repos
        self.translator = translator
        self.logger = get_logger()

    @staticmethod
    def _ingredient_needs_parsing(ingredient: RecipeIngredient) -> bool:
        has_structured_fields = bool(ingredient.quantity or ingredient.unit or ingredient.food)
        return bool((ingredient.note or ingredient.display or "").strip() and not has_structured_fields)

    @staticmethod
    def _parsed_ingredient_is_useful(ingredient: RecipeIngredient) -> bool:
        food_has_id = bool(ingredient.food and getattr(ingredient.food, "id", None))
        unit_has_id = bool(ingredient.unit and getattr(ingredient.unit, "id", None))
        unit_is_safe = not ingredient.unit or unit_has_id
        return food_has_id and unit_is_safe

    async def _auto_parse_ai_ingredients(self, recipe: Recipe) -> Recipe:
        if not getattr(self.repos, "session", None):
            return recipe

        ingredients = recipe.recipe_ingredient or []
        targets = [
            (index, ingredient, (ingredient.note or ingredient.display or "").strip())
            for index, ingredient in enumerate(ingredients)
            if self._ingredient_needs_parsing(ingredient)
        ]
        if not targets:
            return recipe

        for parser_type in (RegisteredParser.openai, RegisteredParser.nlp):
            try:
                parser = get_parser(parser_type, self.repos.group_id, self.repos.session, self.translator)
                parsed = await parser.parse([text for _, _, text in targets])
                if len(parsed) != len(targets):
                    raise ValueError(f"{parser_type} returned {len(parsed)} ingredients for {len(targets)} inputs")

                useful_count = 0
                for (index, original, _), parsed_ingredient in zip(targets, parsed, strict=True):
                    ingredient = parsed_ingredient.ingredient
                    if not self._parsed_ingredient_is_useful(ingredient):
                        ingredients[index] = original
                        continue

                    useful_count += 1
                    ingredients[index] = ingredient

                if useful_count:
                    recipe.recipe_ingredient = ingredients
                    return recipe
            except Exception:
                self.logger.exception(f"Failed to auto-parse imported ingredients with {parser_type}")

        return recipe

    async def scrape(
        self,
        url: str,
        html: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[Recipe, ScrapedExtras] | tuple[None, None]:
        """
        Scrapes a recipe from the web.
        Skips the network request if `html` is provided.
        Optionally reports progress back via `on_progress`.
        """

        if not html:
            if on_progress:
                await on_progress(self.translator.t("recipe.create-progress.fetching-webpage"))

            html = await safe_scrape_html(url)
            if not html:
                return None, None

        for ScraperClass in self.scrapers:
            scraper = ScraperClass(url, self.translator, self.repos, raw_html=html)
            if not scraper.can_scrape():
                self.logger.debug(f"Skipping {scraper.__class__.__name__}")
                continue

            try:
                result = await scraper.parse(on_progress=on_progress)
            except Exception:
                self.logger.exception(f"Failed to scrape HTML with {scraper.__class__.__name__}")
                result = None

            if result is None or result[0] is None:
                continue

            recipe_result, extras = result
            try:
                recipe = cleaner.clean(recipe_result, self.translator)
            except Exception:
                self.logger.exception(f"Failed to clean recipe data from {scraper.__class__.__name__}")
                continue

            if isinstance(scraper, (RecipeScraperOpenAITranscription, RecipeScraperOpenAI)):
                recipe = await self._auto_parse_ai_ingredients(recipe)

            return recipe, extras

        return None, None
