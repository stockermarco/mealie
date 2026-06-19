import json
from html import escape
from types import SimpleNamespace

import pytest

from mealie.lang.providers import get_locale_provider
from mealie.schema.openai.general import OpenAIText
from mealie.schema.recipe.recipe import Recipe
from mealie.schema.recipe.recipe_ingredient import RecipeIngredient
from mealie.schema.recipe.recipe_step import RecipeStep
from mealie.services.openai import OpenAIService
from mealie.services.scraper.recipe_scraper import RecipeScraper
from mealie.services.scraper.scraped_extras import ScrapedExtras
from mealie.services.scraper.scraper_strategies import (
    MAX_OPEN_GRAPH_TEXT_LENGTH,
    OPEN_GRAPH_PLACEHOLDER_INGREDIENT,
    OPEN_GRAPH_PLACEHOLDER_INSTRUCTION,
    ABCScraperStrategy,
    RecipeScraperOpenAI,
    RecipeScraperOpenGraph,
    RecipeScraperPackage,
)


class FakeProviderSettings:
    def __init__(self, ai_enabled: bool):
        self.settings = SimpleNamespace(ai_enabled=ai_enabled)

    def get_one(self, group_id):
        return self.settings


class FakeRepos:
    group_id = "test-group"

    def __init__(self, ai_enabled: bool):
        self.group_ai_provider_settings = FakeProviderSettings(ai_enabled)


def scraper(scraper_cls, url: str, html: str, ai_enabled: bool = True):
    return scraper_cls(url, get_locale_provider(), FakeRepos(ai_enabled), raw_html=html)


def social_html(title: str, description: str, image: str = "https://cdn.example.com/recipe.jpg?utm_source=ig") -> str:
    return f"""
    <html>
      <head>
        <meta property="og:title" content="{escape(title, quote=True)}">
        <meta property="og:description" content="{escape(description, quote=True)}">
        <meta property="og:image" content="{escape(image, quote=True)}">
      </head>
      <body>Instagram</body>
    </html>
    """


def recipe_json_ld_html() -> str:
    return RecipeScraperPackage.ld_json_to_html(
        json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "Recipe",
                "name": "Simple Salad",
                "recipeIngredient": ["1 cucumber", "2 tomatoes"],
                "recipeInstructions": [{"@type": "HowToStep", "text": "Slice vegetables."}],
            }
        )
    )


class FailingTranscriptionScraper(ABCScraperStrategy):
    def can_scrape(self) -> bool:
        return True

    async def get_html(self, url: str) -> str:
        return self.raw_html or ""

    async def parse(self, on_progress=None):
        raise RuntimeError("mock transcription failure")


class CapturingOpenAIScraper(RecipeScraperOpenAI):
    async def parse(self, on_progress=None):
        message = self.format_html_to_text(self.raw_html or "")
        assert "Zutaten: 250 g Pasta" in message
        return (
            Recipe(
                name="Cremige Tomatenpasta",
                recipe_ingredient=[RecipeIngredient(note="250 g Pasta")],
                recipe_instructions=[RecipeStep(text="Pasta kochen.")],
            ),
            ScrapedExtras(),
        )


def test_openai_input_includes_opengraph_caption_without_tracking_params():
    signed_image_url = "https://cdn.example.com/recipe.jpg?Expires=123&Signature=abc&Key-Pair-Id=key"
    html = social_html(
        "cookwithmaria on Instagram: Cremige Tomatenpasta",
        "Zutaten: 250 g Pasta, 2 Tomaten. Schritte: Pasta kochen. Sauce ruehren.",
        image=signed_image_url,
    )
    strategy = scraper(
        RecipeScraperOpenAI,
        "https://www.instagram.com/reel/abc123/?utm_source=ig_web_copy_link&igsh=tracking",
        html,
    )

    message = strategy.format_html_to_text(html)

    assert "OpenGraph title:" in message
    assert "OpenGraph description:" in message
    assert "Visible page text:" in message
    assert "Zutaten: 250 g Pasta" in message
    assert "Pasta kochen" in message
    assert "Source URL:\nhttps://www.instagram.com/reel/abc123/" in message
    assert "utm_source" not in message
    assert "igsh" not in message
    assert f"Recipe Image: {signed_image_url}" in message


def test_openai_input_handles_caption_special_characters():
    caption = 'Zutaten:\n- 2 Äpfel & "Rahm" 🥣\nSchritte: rühren, backen.\n#dessert'
    html = social_html('Müllers "Apfelküchlein" & mehr', caption)
    strategy = scraper(RecipeScraperOpenAI, "https://instagram.com/reel/abc123/", html)

    message = strategy.format_html_to_text(html)

    assert 'Müllers "Apfelküchlein" & mehr' in message
    assert '2 Äpfel & "Rahm" 🥣' in message
    assert "Schritte: rühren, backen." in message
    assert "#dessert" in message


def test_opengraph_caption_is_length_limited():
    long_description = "A" * (MAX_OPEN_GRAPH_TEXT_LENGTH + 500)
    html = social_html("Short title", long_description)
    strategy = scraper(RecipeScraperOpenAI, "https://www.instagram.com/reel/abc123/", html)

    message = strategy.format_html_to_text(html)

    assert "A" * MAX_OPEN_GRAPH_TEXT_LENGTH in message
    assert "A" * (MAX_OPEN_GRAPH_TEXT_LENGTH + 1) not in message


@pytest.mark.asyncio
async def test_json_ld_recipe_still_works_with_package_scraper_first():
    strategy = scraper(RecipeScraperPackage, "https://example.com/recipe", recipe_json_ld_html(), ai_enabled=False)

    scraped = await strategy.scrape_url()

    assert scraped is not None
    assert scraped.title() == "Simple Salad"
    assert scraped.ingredients() == ["1 cucumber", "2 tomatoes"]


@pytest.mark.asyncio
async def test_caption_only_reel_can_fall_through_to_web_ai_after_transcription_failure():
    html = social_html(
        "cookwithmaria on Instagram: Cremige Tomatenpasta",
        "Zutaten: 250 g Pasta, 2 Tomaten. Schritte: Pasta kochen. Sauce ruehren.",
    )
    recipe_scraper = RecipeScraper(
        FakeRepos(ai_enabled=True),
        get_locale_provider(),
        scrapers=[FailingTranscriptionScraper, CapturingOpenAIScraper, RecipeScraperOpenGraph],
    )

    recipe, _ = await recipe_scraper.scrape("https://www.instagram.com/reel/abc123/", html)

    assert recipe is not None
    assert recipe.name == "Cremige Tomatenpasta"
    assert recipe.recipe_ingredient[0].note == "250 g Pasta"
    assert recipe.recipe_instructions[0].text == "Pasta kochen."


@pytest.mark.asyncio
async def test_social_opengraph_caption_becomes_structured_recipe(monkeypatch: pytest.MonkeyPatch):
    html = social_html(
        "cookwithmaria on Instagram: Cremige Tomatenpasta",
        "Cremige Tomatenpasta. Zutaten: 250 g Pasta, 2 Tomaten. Schritte: Pasta kochen. Sauce ruehren.",
        image="https://cdn.example.com/recipe.jpg?Expires=123&Signature=abc",
    )
    recipe_url = "https://www.instagram.com/reel/abc123/?utm_source=ig_web_copy_link&igsh=tracking"
    captured = {}

    async def mock_get_response(self, prompt, message, *args, **kwargs) -> OpenAIText:
        captured["prompt"] = prompt
        captured["message"] = message
        captured["schema"] = kwargs.get("response_schema")
        return OpenAIText(
            text=json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "Recipe",
                    "name": "Cremige Tomatenpasta",
                    "description": "Schnelle Tomatenpasta aus der Reel-Caption.",
                    "recipeIngredient": ["250 g Pasta", "2 Tomaten"],
                    "recipeInstructions": [
                        {"@type": "HowToStep", "text": "Pasta kochen."},
                        {"@type": "HowToStep", "text": "Sauce ruehren."},
                    ],
                }
            )
        )

    monkeypatch.setattr(OpenAIService, "__init__", lambda self, repos: None)
    monkeypatch.setattr(OpenAIService, "get_prompt", lambda self, name: f"prompt:{name}")
    monkeypatch.setattr(OpenAIService, "get_response", mock_get_response)

    recipe, _ = await scraper(RecipeScraperOpenAI, recipe_url, html).parse()

    assert captured["prompt"] == "prompt:recipes.scrape-recipe"
    assert captured["schema"] is OpenAIText
    assert "OpenGraph title:" in captured["message"]
    assert "OpenGraph description:" in captured["message"]
    assert "utm_source" not in captured["message"]
    assert "igsh" not in captured["message"]
    assert recipe.name == "Cremige Tomatenpasta"
    assert recipe.description == "Schnelle Tomatenpasta aus der Reel-Caption."
    assert [ingredient.note for ingredient in recipe.recipe_ingredient] == ["250 g Pasta", "2 Tomaten"]
    assert [step.text for step in recipe.recipe_instructions] == ["Pasta kochen.", "Sauce ruehren."]
    assert recipe.org_url == recipe_url


@pytest.mark.asyncio
async def test_social_opengraph_fallback_is_blocked_when_ai_is_enabled():
    strategy = scraper(
        RecipeScraperOpenGraph,
        "https://www.instagram.com/reel/abc123/",
        social_html("cookwithmaria on Instagram: Caption", "Caption without structured AI result"),
        ai_enabled=True,
    )

    result = await strategy.parse()

    assert result is None


@pytest.mark.asyncio
async def test_social_opengraph_fallback_is_preserved_when_ai_is_disabled():
    strategy = scraper(
        RecipeScraperOpenGraph,
        "https://www.instagram.com/reel/abc123/",
        social_html("cookwithmaria on Instagram: Caption", "Caption without structured AI result"),
        ai_enabled=False,
    )

    recipe, _ = await strategy.parse()

    assert recipe.name.startswith("cookwithmaria on Instagram")
    assert recipe.recipe_ingredient[0].note == OPEN_GRAPH_PLACEHOLDER_INGREDIENT
    assert recipe.recipe_instructions[0].text == OPEN_GRAPH_PLACEHOLDER_INSTRUCTION


@pytest.mark.asyncio
async def test_non_social_opengraph_fallback_is_preserved_when_ai_is_enabled():
    strategy = scraper(
        RecipeScraperOpenGraph,
        "https://example.com/post",
        social_html("Example: Caption", "Caption without structured recipe data"),
        ai_enabled=True,
    )

    recipe, _ = await strategy.parse()

    assert recipe.name == "Example: Caption"
    assert recipe.recipe_ingredient[0].note == OPEN_GRAPH_PLACEHOLDER_INGREDIENT
    assert recipe.recipe_instructions[0].text == OPEN_GRAPH_PLACEHOLDER_INSTRUCTION


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/reel/abc123/",
        "https://instagram.com/reel/abc123/",
        "https://m.facebook.com/watch/?v=abc123",
        "https://vm.tiktok.com/abc123/",
        "https://youtube.com/watch?v=abc123",
        "https://youtu.be/abc123",
        "https://pin.it/abc123",
    ],
)
def test_social_media_host_detection(url: str):
    assert RecipeScraperOpenAI.is_social_media_url(url)


@pytest.mark.parametrize("url", ["https://notinstagram.com/reel/abc123/", "https://example.com/recipe"])
def test_social_media_host_detection_rejects_non_social_hosts(url: str):
    assert not RecipeScraperOpenAI.is_social_media_url(url)


def test_social_ai_recipe_must_not_have_placeholder_or_caption_title():
    strategy = scraper(RecipeScraperOpenAI, "https://www.instagram.com/reel/abc123/", "<html></html>")
    bad_recipe = Recipe(
        name="cookwithmaria on Instagram: Zutaten: 250 g Pasta, 2 Tomaten, 100 ml Rahm",
        recipe_ingredient=[RecipeIngredient(note=OPEN_GRAPH_PLACEHOLDER_INGREDIENT)],
        recipe_instructions=[RecipeStep(text=OPEN_GRAPH_PLACEHOLDER_INSTRUCTION)],
    )
    good_recipe = Recipe(
        name="Cremige Tomatenpasta",
        recipe_ingredient=[RecipeIngredient(note="250 g Pasta")],
        recipe_instructions=[RecipeStep(text="Pasta kochen.")],
    )

    assert not strategy.is_usable_social_ai_recipe(bad_recipe)
    assert strategy.is_usable_social_ai_recipe(good_recipe)
