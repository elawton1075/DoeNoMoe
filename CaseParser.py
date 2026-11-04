"""
CaseParser.py

Reusable case parser for Missing Persons and Unidentified Persons full payloads.
Builds typed CaseModels objects, then serializes them for dict based callers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from CaseModels import (
    AgencyDetails,
    AgencySelection,
    CaseAge,
    CaseBreakdown,
    CaseCircumstances,
    CaseDemographics,
    CaseIdentifiers,
    CaseMedia,
    CasePhysicalDescription,
    ClothingAndAccessories,
    ClothingItem,
    InvestigatingAgency,
    NamedValue,
    ParsedCase,
    PhysicalFeatureItem,
    PhysicalFeatures,
    ValueRange,
)

# Keys tried, in order, to turn a NamUs lookup object ({"name": ...}) into text.
_NAME_KEYS = ("displayName", "name", "label", "value", "description")


class CaseParser:
    """Parse a NamUs full case payload into typed models and flattened fields."""

    PRUNED_PARSED_BLOBS: Set[str] = {
        "caseIdentification",
        "subjectIdentification",
        "subjectDescription",
        "physicalDescription",
        "physicalFeatureDescriptions",
        "clothingAndAccessoriesArticles",
        "investigatingAgencies",
        "circumstances",
        "sighting",
    }

    def parse_case_object(self, case: Dict[str, Any], case_set: str) -> ParsedCase:
        """Return a typed parsed object for one case."""
        case_data = dict(case)
        return ParsedCase(raw_case=case_data, breakdown=self._build_breakdown(case_data, case_set))

    def parse_case(self, case: Dict[str, Any], case_set: str) -> Dict[str, Any]:
        """Return a serialized parsed case for dict based callers."""
        return self.parse_case_object(case, case_set).to_output_dict(self.PRUNED_PARSED_BLOBS)

    def parse_case_objects(self, cases: List[Dict[str, Any]], case_set: str) -> List[ParsedCase]:
        """Tag each raw case with its case set and parse it, leaving the inputs untouched."""
        return [self.parse_case_object({**case, "Case Set": case_set}, case_set) for case in cases]

    def parse_cases(self, cases: List[Dict[str, Any]], case_set: str) -> List[Dict[str, Any]]:
        """Like parse_case_objects, but returns serialized dicts."""
        return [
            parsed.to_output_dict(self.PRUNED_PARSED_BLOBS)
            for parsed in self.parse_case_objects(cases, case_set)
        ]

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _section(case: Dict[str, Any], key: str) -> Dict[str, Any]:
        """Return a nested object, or an empty dict when missing."""
        value = case.get(key)
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _dict_items(case: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
        """Return the dict entries of a list field, or an empty list when missing."""
        return [item for item in case.get(key) or [] if isinstance(item, dict)]

    @staticmethod
    def _count(case: Dict[str, Any], key: str) -> int:
        value = case.get(key)
        return len(value) if isinstance(value, list) else 0

    @staticmethod
    def _text(value: Any) -> str:
        """Turn a string, number, or NamUs lookup object into stripped text."""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (bool, int, float)):
            return str(value)
        if isinstance(value, dict):
            for key in _NAME_KEYS:
                v = value.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return ""

    def _first_text(self, *values: Any) -> str:
        return next((text for text in map(self._text, values) if text), "")

    def _pick(self, source: Dict[str, Any], *keys: str) -> str:
        """First non-empty text among the given keys of ``source``."""
        return self._first_text(*(source.get(key) for key in keys))

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            return None if value in (None, "") else int(value)
        except (TypeError, ValueError):
            return None

    def _first_int(self, *values: Any) -> Optional[int]:
        """Integer form of ``a or b or c`` over the given values."""
        chosen = None
        for value in values:
            chosen = value
            if value:
                break
        return self._to_int(chosen)

    def _address(self, case: Dict[str, Any]) -> Dict[str, Any]:
        circumstances_address = self._section(self._section(case, "circumstances"), "address")
        return circumstances_address or self._section(self._section(case, "sighting"), "address")

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------
    def _build_identifier_block(self, case: Dict[str, Any]) -> CaseIdentifiers:
        ident = self._section(case, "caseIdentification")
        return CaseIdentifiers(
            id=case.get("id"),
            case_number=ident.get("caseNumber") or case.get("caseNumber"),
            ncmec_number=ident.get("ncmecNumber"),
            namus_number=ident.get("namusNumber"),
            agency_case_number=ident.get("agencyCaseNumber"),
            case_set=case.get("Case Set"),
            case_link=case.get("Case Link"),
            case_resolved=bool(case.get("caseIsResolved", False)),
        )

    def _build_demographics_block(self, case: Dict[str, Any]) -> CaseDemographics:
        desc = self._section(case, "subjectDescription")
        ident = self._section(case, "subjectIdentification")

        def either(key: str) -> str:
            return self._first_text(desc.get(key), ident.get(key))

        first, middle, last = (self._pick(ident, k) for k in ("firstName", "middleName", "lastName"))
        return CaseDemographics(
            name=" ".join(part for part in (first, middle, last) if part),
            first_name=first,
            middle_name=middle,
            last_name=last,
            date_of_birth=ident.get("computedDateOfBirth") or ident.get("dateOfBirth"),
            year_of_birth=self._to_int(ident.get("yearOfBirth")),
            sex=either("sex"),
            gender=either("gender"),
            primary_ethnicity=either("primaryEthnicity"),
            primary_race=either("primaryRace"),
        )

    @staticmethod
    def _year(value: Any) -> Optional[int]:
        """Year from a date string like "1986-03-04"."""
        text = str(value or "")[:4]
        return int(text) if text.isdigit() else None

    @staticmethod
    def _value_range(low: Optional[int], high: Optional[int]) -> ValueRange:
        """Build a range, filling a missing bound from the other one."""
        return ValueRange(
            min_value=low if low is not None else high,
            max_value=high if high is not None else low,
        )

    @classmethod
    def _project_birth_years(cls, age: ValueRange, on_date: Any) -> ValueRange:
        """Birth years that fit an age range on a given date.

        An age of N means N <= age < N + 1, so the oldest possible birth year is
        year - max_age - 1 and the youngest is year - min_age.
        """
        year = cls._year(on_date)
        if not age.is_known or year is None:
            return ValueRange()
        return ValueRange(min_value=year - age.max_value - 1, max_value=year - age.min_value)

    def _last_contact_date(self, case: Dict[str, Any]) -> Any:
        """When a missing person was last seen or heard from."""
        circumstances = self._section(case, "circumstances")
        return circumstances.get("dateOfLastContact") or self._section(case, "sighting").get("date")

    def _build_age_block(self, case: Dict[str, Any], case_set: str) -> CaseAge:
        if case_set == "Missing Persons":
            ident = self._section(case, "subjectIdentification")
            when_missing = self._value_range(
                self._to_int(ident.get("computedMissingMinAge")),
                self._to_int(ident.get("computedMissingMaxAge")),
            )
            now = self._value_range(
                self._to_int(ident.get("currentMinAge")),
                self._to_int(ident.get("currentMaxAge")),
            )

            # An exact birth date or year beats a projection from the age when missing.
            birth_year = self._year(ident.get("computedDateOfBirth") or ident.get("dateOfBirth"))
            if birth_year is None:
                birth_year = self._to_int(ident.get("yearOfBirth"))
            if birth_year is not None:
                projected = ValueRange(birth_year, birth_year)
            else:
                projected = self._project_birth_years(when_missing, self._last_contact_date(case))
            return CaseAge(when_missing=when_missing, now=now, projected_birth_years=projected)

        # Unidentified: age is an estimate at the time found, so project birth years.
        desc = self._section(case, "subjectDescription")
        estimated = self._value_range(
            self._to_int(desc.get("estimatedAgeFrom")),
            self._to_int(desc.get("estimatedAgeTo")),
        )
        projected = self._project_birth_years(
            estimated, self._section(case, "circumstances").get("dateFound")
        )
        return CaseAge(
            when_missing=ValueRange(),
            now=ValueRange(),
            projected_birth_years=projected,
            projected_age_at_death=estimated,
        )

    def _build_physical_description_block(self, case: Dict[str, Any]) -> CasePhysicalDescription:
        pd = self._section(case, "physicalDescription")
        # Unidentified payloads keep height and weight under subjectDescription.
        sd = self._section(case, "subjectDescription")
        return CasePhysicalDescription(
            height_min_inches=self._first_int(pd.get("heightFrom"), pd.get("heightMin"), sd.get("heightFrom")),
            height_max_inches=self._first_int(pd.get("heightTo"), pd.get("heightMax"), sd.get("heightTo")),
            weight_min_pounds=self._first_int(pd.get("weightFrom"), pd.get("weightMin"), sd.get("weightFrom")),
            weight_max_pounds=self._first_int(pd.get("weightTo"), pd.get("weightMax"), sd.get("weightTo")),
            eye_color=self._pick(pd, "eyeColor", "leftEyeColor", "rightEyeColor"),
            hair_color=self._pick(pd, "hairColor"),
            head_hair=self._pick(pd, "headHairDescription", "headHair", "hairDescription"),
            facial_hair=self._pick(pd, "facialHair"),
            distinctive_features=self._pick(pd, "distinctiveFeatures", "description"),
        )

    def _build_clothing_block(self, case: Dict[str, Any]) -> ClothingAndAccessories:
        return ClothingAndAccessories(
            items=[
                ClothingItem(
                    category=self._pick(article, "articleCategory", "category", "article"),
                    type=self._pick(article, "articleType", "type"),
                    color=self._pick(article, "color"),
                    size=self._pick(article, "size"),
                    brand=self._pick(article, "brand"),
                    description=self._pick(article, "description", "additionalDescription", "comments", "comment"),
                )
                for article in self._dict_items(case, "clothingAndAccessoriesArticles")
            ]
        )

    def _build_physical_features_block(self, case: Dict[str, Any]) -> PhysicalFeatures:
        return PhysicalFeatures(
            items=[
                PhysicalFeatureItem(
                    type=self._pick(feature, "physicalFeatureType", "physicalFeature", "type", "feature"),
                    location=self._pick(feature, "bodyLocation", "location"),
                    value=self._pick(feature, "value"),
                    description=self._pick(feature, "description", "additionalDescription", "comments", "comment"),
                )
                for feature in self._dict_items(case, "physicalFeatureDescriptions")
            ]
        )

    def _build_circumstances_block(self, case: Dict[str, Any]) -> CaseCircumstances:
        circumstances = self._section(case, "circumstances")
        address = self._address(case)
        return CaseCircumstances(
            status=self._pick(circumstances, "status"),
            date_found=circumstances.get("dateFound"),
            date_body_found=circumstances.get("dateBodyFound"),
            date_last_contact=self._last_contact_date(case),
            city=address.get("city"),
            county=self._pick(address, "county"),
            state=self._pick(address, "state"),
            country=self._pick(address, "country"),
            zip_code=address.get("zip") or address.get("postalCode") or address.get("zipCode"),
            circumstances_of_disappearance=circumstances.get("circumstancesOfDisappearance"),
            circumstances_of_recovery=circumstances.get("circumstancesOfRecovery"),
        )

    def _build_named_value(self, value: Any) -> Optional[NamedValue]:
        if not isinstance(value, dict):
            return None
        return NamedValue(
            id=value.get("id"),
            name=value.get("name"),
            localized_name=value.get("localizedName"),
            display_name=value.get("displayName"),
        )

    def _build_agency_details(self, agency: Any) -> Optional[AgencyDetails]:
        if not isinstance(agency, dict):
            return None
        return AgencyDetails(
            id=agency.get("id"),
            name=agency.get("name"),
            street1=agency.get("street1"),
            city=agency.get("city"),
            county=self._build_named_value(agency.get("county")),
            zip_code=agency.get("zipCode"),
            state=self._build_named_value(agency.get("state")),
            phone=agency.get("phone"),
            jurisdiction=self._build_named_value(agency.get("jurisdiction")),
            agency_type=self._build_named_value(agency.get("agencyType")),
            approved=agency.get("approved"),
            website_url=agency.get("websiteUrl"),
        )

    def _build_agency_selection(self, selection: Any) -> Optional[AgencySelection]:
        if not isinstance(selection, dict):
            return None
        return AgencySelection(
            id=selection.get("id"),
            agency=self._build_agency_details(selection.get("agency")),
        )

    def _build_agencies_block(self, case: Dict[str, Any]) -> List[InvestigatingAgency]:
        return [
            InvestigatingAgency(
                id=agency.get("id"),
                is_case_owner=agency.get("isCaseOwner"),
                name=agency.get("name"),
                city=agency.get("city"),
                state=self._build_named_value(agency.get("state")),
                county=self._build_named_value(agency.get("county")),
                selection=self._build_agency_selection(agency.get("selection")),
                case_number=agency.get("caseNumber"),
                date_reported=agency.get("dateReported"),
            )
            for agency in self._dict_items(case, "investigatingAgencies")
        ]

    def _build_media_block(self, case: Dict[str, Any]) -> CaseMedia:
        has_photo = any(
            case.get(key)
            for key in ("images", "defaultImage", "hrefDefaultImageThumbnail", "hrefDefaultImagePoster")
        )
        return CaseMedia(
            has_photo=has_photo,
            image_count=self._count(case, "images"),
            document_count=self._count(case, "documents"),
        )

    def _build_breakdown(self, case: Dict[str, Any], case_set: str) -> CaseBreakdown:
        return CaseBreakdown(
            identifiers=self._build_identifier_block(case),
            demographics=self._build_demographics_block(case),
            age=self._build_age_block(case, case_set),
            physical_description=self._build_physical_description_block(case),
            clothing_and_accessories=self._build_clothing_block(case),
            physical_features=self._build_physical_features_block(case),
            circumstances=self._build_circumstances_block(case),
            investigating_agencies=self._build_agencies_block(case),
            media=self._build_media_block(case),
            vehicles_count=self._count(case, "vehicles"),
            top_level_keys=sorted(case.keys()),
        )


