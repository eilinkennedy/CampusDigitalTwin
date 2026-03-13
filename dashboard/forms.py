from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Building, EnergyConsumption, Event, Path, PhaseOccupancy


INPUT_CLASSES = (
    "w-full rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 "
    "text-sm text-slate-700 shadow-sm outline-none transition "
    "focus:border-primary focus:ring-4 focus:ring-primary/10"
)

CHECKBOX_CLASSES = "h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary/30"


class StyledAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASSES,
                "placeholder": "Enter your username",
                "autofocus": True,
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASSES,
                "placeholder": "Enter your password",
            }
        )
    )


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = CHECKBOX_CLASSES
            else:
                existing_class = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing_class} {INPUT_CLASSES}".strip()


class BuildingForm(StyledModelForm):
    class Meta:
        model = Building
        fields = "__all__"


class EventForm(StyledModelForm):
    class Meta:
        model = Event
        fields = "__all__"
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "locations": forms.SelectMultiple(attrs={"size": 6}),
        }


class PhaseOccupancyForm(StyledModelForm):
    class Meta:
        model = PhaseOccupancy
        fields = "__all__"


class PathForm(StyledModelForm):
    class Meta:
        model = Path
        fields = "__all__"
        widgets = {
            "direction_hint": forms.Textarea(attrs={"rows": 4}),
        }


class EnergyConsumptionForm(StyledModelForm):
    class Meta:
        model = EnergyConsumption
        fields = "__all__"
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }