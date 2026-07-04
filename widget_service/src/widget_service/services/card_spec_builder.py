from widget_service.models.generation import CandidateDataBinding, CardSpec, WidgetSize


class CardSpecBuilder:
    def build(self, size: WidgetSize, effective_bindings: list[CandidateDataBinding]) -> CardSpec:
        if not effective_bindings:
            return CardSpec(suggestSize=size)
        return CardSpec(suggestSize=size, dataBindings=effective_bindings)
