import pandas as pd

COLUMNS = ["day", "model", "model_family", "routed", "ai_credits_used"]


def model_family(model):
    """Tag a model name with its family (same rules as model-to-final.sh)."""
    for key in ("Opus", "Sonnet", "Haiku", "GPT", "Gemini"):
        if key in model:
            return key
    if model == "Code Review model":
        return "CodeReview"
    return "Other"


def build_model_rows(usage_items, report_day):
    """Group billing usageItems by model, sum grossQuantity, tag family/routed."""
    if not usage_items:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(usage_items)
    grouped = (
        df.groupby("model", as_index=False)["grossQuantity"].sum()
        .rename(columns={"grossQuantity": "ai_credits_used"})
    )
    grouped["model_family"] = grouped["model"].apply(model_family)
    grouped["routed"] = grouped["model"].str.startswith("Auto:")
    grouped["day"] = report_day
    return (
        grouped[COLUMNS]
        .sort_values("ai_credits_used", ascending=False)
        .reset_index(drop=True)
    )
