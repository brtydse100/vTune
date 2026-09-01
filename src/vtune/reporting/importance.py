"""Exploratory parameter-importance report component."""

from html import escape

from vtune.managers.scoring import TrialScore
from vtune.reporting.analysis import parameter_importance


def importance_section(ranking: tuple[TrialScore, ...]) -> str:
    if len(ranking) < 5:
        return ("<p class='muted'>Not shown: fewer than 5 eligible tuned trials. "
                "A percentage here would look precise without enough evidence.</p>")
    values = parameter_importance(ranking)
    confidence = ("Exploratory association across evaluated trials, not causation. "
                  "For each setting, vTune groups trial scores by observed value and "
                  "measures how far each group mean is from the overall mean. The "
                  "displayed percentages normalize those differences to 100%.")
    bars = "".join(
        f"<div class='hbar'><span>{escape(name)}</span>"
        f"<i style='width:{value * 70:.1f}%'></i><b>{value:.1%}</b></div>"
        for name, value in values.items()
    ) or "<p class='muted'>Not enough varied trials to estimate importance.</p>"
    return f"<p class='note'>{confidence}</p>{bars}"
