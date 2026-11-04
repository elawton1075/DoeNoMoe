"""
CaseParser.py

Reusable case parser for Missing Persons and Unidentified Persons full payloads.
Produces a structured breakdown and flattened top level fields.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple


class CaseParser:
    """Parse a NamUs full case payload into structured and flattened fields."""

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

    def parse_case(self, case: Dict[str, Any], case_set: str) -> Dict[str, Any]:
        """Return a parsed copy of one case for the requested case set."""
        parsed = dict(case)
        parsed["Breakdown"] = self._build_breakdown(parsed, case_set)
        parsed["Eye Color"] = parsed["Breakdown"].get("Eye Color", "")
        parsed["Hair Color"] = parsed["Breakdown"].get("Hair Color", "")
        parsed["Physical Features Summary"] = parsed["Breakdown"].get("Physical Features Summary", "")
        parsed["Investigating Agency Summary"] = parsed["Breakdown"].get("Investigating Agencies Summary", "")
        self._prune_parsed_blobs(parsed)
        return parsed

    def _extract_name(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("displayName", "name", "label", "value", "description"):
                v = value.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return ""

    def _value_to_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            named = self._extract_name(value)
            if named:
                return named
        return ""

    def _to_int(self, value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _first_text(self, *values: Any) -> str:
        for value in values:
            text = self._value_to_text(value)
            if text:
                return text
        return ""

    def _get_address(self, case: Dict[str, Any]) -> Dict[str, Any]:
        circ_addr = (case.get("circumstances") or {}).get("address") or {}
        sight_addr = (case.get("sighting") or {}).get("address") or {}
        return circ_addr or sight_addr

    def _has_photo(self, case: Dict[str, Any]) -> bool:
        images = case.get("images")
        if isinstance(images, list) and len(images) > 0:
            return True
        default_image = case.get("defaultImage")
        if isinstance(default_image, dict) and len(default_image) > 0:
            return True
        return bool(case.get("hrefDefaultImageThumbnail") or case.get("hrefDefaultImagePoster"))

    def _extract_age_range(self, case: Dict[str, Any], case_set: str) -> Tuple[Optional[int], Optional[int]]:
        if case_set == "Missing Persons":
            ident = case.get("subjectIdentification") or {}
            min_age = self._to_int(ident.get("computedMissingMinAge") or ident.get("currentMinAge"))
            max_age = self._to_int(ident.get("computedMissingMaxAge") or ident.get("currentMaxAge"))
            if max_age is None:
                max_age = min_age
            return min_age, max_age

        subj = case.get("subjectDescription") or {}
        min_age = self._to_int(subj.get("estimatedAgeFrom"))
        max_age = self._to_int(subj.get("estimatedAgeTo"))
        if max_age is None:
            max_age = min_age
        return min_age, max_age

    def _build_identifier_block(self, case: Dict[str, Any]) -> Dict[str, Any]:
        ident = case.get("caseIdentification") or {}
        return {
            "ID": case.get("id"),
            "Formatted ID": case.get("idFormatted"),
            "Case Number": ident.get("caseNumber") or case.get("caseNumber"),
            "NCMEC Number": ident.get("ncmecNumber"),
            "NamUs Number": ident.get("namusNumber"),
            "Agency Case Number": ident.get("agencyCaseNumber"),
            "Case Set": case.get("Case Set"),
            "Case Link": case.get("Case Link"),
            "Status": self._first_text((case.get("circumstances") or {}).get("status")),
            "Case Resolved": bool(case.get("caseIsResolved", False)),
        }

    def _build_demographics_block(self, case: Dict[str, Any]) -> Dict[str, Any]:
        subj_desc = case.get("subjectDescription") or {}
        subj_ident = case.get("subjectIdentification") or {}

        first_name = self._first_text(subj_ident.get("firstName"))
        middle_name = self._first_text(subj_ident.get("middleName"))
        last_name = self._first_text(subj_ident.get("lastName"))
        full_name = " ".join(x for x in [first_name, middle_name, last_name] if x).strip()

        return {
            "Name": full_name,
            "First Name": first_name,
            "Middle Name": middle_name,
            "Last Name": last_name,
            "Date of Birth": subj_ident.get("computedDateOfBirth") or subj_ident.get("dateOfBirth"),
            "Year of Birth": self._to_int(subj_ident.get("yearOfBirth")),
            "Sex": self._first_text(subj_desc.get("sex"), subj_ident.get("sex")),
            "Gender": self._first_text(subj_desc.get("gender"), subj_ident.get("gender")),
            "Primary Ethnicity": self._first_text(
                subj_desc.get("primaryEthnicity"),
                subj_ident.get("primaryEthnicity"),
            ),
            "Primary Race": self._first_text(
                subj_desc.get("primaryRace"),
                subj_ident.get("primaryRace"),
            ),
        }

    def _build_age_block(self, case: Dict[str, Any], case_set: str) -> Dict[str, Any]:
        min_age, max_age = self._extract_age_range(case, case_set)
        subj_desc = case.get("subjectDescription") or {}
        subj_ident = case.get("subjectIdentification") or {}
        return {
            "Min": min_age,
            "Max": max_age,
            "Estimated Min": self._to_int(subj_desc.get("estimatedAgeFrom")),
            "Estimated Max": self._to_int(subj_desc.get("estimatedAgeTo")),
            "Missing Min": self._to_int(subj_ident.get("computedMissingMinAge") or subj_ident.get("currentMinAge")),
            "Missing Max": self._to_int(subj_ident.get("computedMissingMaxAge") or subj_ident.get("currentMaxAge")),
        }

    def _build_physical_description_block(self, case: Dict[str, Any]) -> Dict[str, Any]:
        pd = case.get("physicalDescription") or {}
        return {
            "Height Min Inches": self._to_int(pd.get("heightFrom") or pd.get("heightMin")),
            "Height Max Inches": self._to_int(pd.get("heightTo") or pd.get("heightMax")),
            "Weight Min Pounds": self._to_int(pd.get("weightFrom") or pd.get("weightMin")),
            "Weight Max Pounds": self._to_int(pd.get("weightTo") or pd.get("weightMax")),
            "Eye Color": self._first_text(pd.get("eyeColor")),
            "Hair Color": self._first_text(pd.get("hairColor")),
            "Head Hair": self._first_text(pd.get("headHair"), pd.get("hairDescription")),
            "Facial Hair": self._first_text(pd.get("facialHair")),
            "Distinctive Features": self._first_text(pd.get("distinctiveFeatures"), pd.get("description")),
        }

    def _build_clothing_block(self, case: Dict[str, Any]) -> Dict[str, Any]:
        articles = case.get("clothingAndAccessoriesArticles") or []
        parsed: List[Dict[str, Any]] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            parsed.append(
                {
                    "Category": self._first_text(article.get("articleCategory"), article.get("category")),
                    "Type": self._first_text(article.get("articleType"), article.get("type")),
                    "Color": self._first_text(article.get("color")),
                    "Size": self._first_text(article.get("size")),
                    "Brand": self._first_text(article.get("brand")),
                    "Description": self._first_text(
                        article.get("description"),
                        article.get("additionalDescription"),
                        article.get("comments"),
                        article.get("comment"),
                    ),
                }
            )
        return {
            "Count": len(parsed),
            "Items": parsed,
        }

    def _build_physical_features_block(self, case: Dict[str, Any]) -> Dict[str, Any]:
        features = case.get("physicalFeatureDescriptions") or []
        parsed: List[Dict[str, Any]] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            parsed.append(
                {
                    "Type": self._first_text(
                        feature.get("physicalFeatureType"),
                        feature.get("physicalFeature"),
                        feature.get("type"),
                        feature.get("feature"),
                    ),
                    "Location": self._first_text(feature.get("bodyLocation"), feature.get("location")),
                    "Value": self._first_text(feature.get("value")),
                    "Description": self._first_text(
                        feature.get("description"),
                        feature.get("additionalDescription"),
                        feature.get("comments"),
                        feature.get("comment"),
                    ),
                }
            )
        return {
            "Count": len(parsed),
            "Items": parsed,
        }

    def _build_circumstances_block(self, case: Dict[str, Any]) -> Dict[str, Any]:
        circumstances = case.get("circumstances") or {}
        address = self._get_address(case)
        return {
            "Status": self._first_text(circumstances.get("status")),
            "Date Found": circumstances.get("dateFound"),
            "Date Body Found": circumstances.get("dateBodyFound"),
            "Date Last Contact": circumstances.get("dateOfLastContact"),
            "City": address.get("city"),
            "County": address.get("county"),
            "State": self._first_text(address.get("state")),
            "Country": self._first_text(address.get("country")),
            "Zip": address.get("zip") or address.get("postalCode"),
            "Circumstances of Disappearance": circumstances.get("circumstancesOfDisappearance"),
            "Circumstances of Recovery": circumstances.get("circumstancesOfRecovery"),
        }

    def _build_agencies_block(self, case: Dict[str, Any]) -> List[str]:
        agencies = case.get("investigatingAgencies") or []
        names: List[str] = []
        for agency in agencies:
            if not isinstance(agency, dict):
                continue
            name = self._first_text(agency.get("name"))
            if name:
                names.append(name)
        return names

    def _summarize_names(self, values: List[str]) -> str:
        unique = [v for v in dict.fromkeys(values) if v]
        return ", ".join(unique)

    def _physical_features_summary(self, physical_features: Dict[str, Any]) -> str:
        items = physical_features.get("Items", [])
        chunks: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            chunks.append(
                self._first_text(
                    item.get("Type"),
                    item.get("Description"),
                    item.get("Value"),
                )
            )
        return self._summarize_names([c for c in chunks if c])

    def _build_media_block(self, case: Dict[str, Any]) -> Dict[str, Any]:
        images = case.get("images") or []
        docs = case.get("documents") or []
        return {
            "Has Photo": self._has_photo(case),
            "Image Count": len(images) if isinstance(images, list) else 0,
            "Document Count": len(docs) if isinstance(docs, list) else 0,
        }

    def _build_breakdown(self, case: Dict[str, Any], case_set: str) -> Dict[str, Any]:
        physical_description = self._build_physical_description_block(case)
        physical_features = self._build_physical_features_block(case)
        agency_names = self._build_agencies_block(case)
        return {
            "Identifiers": self._build_identifier_block(case),
            "Demographics": self._build_demographics_block(case),
            "Age": self._build_age_block(case, case_set),
            "Physical Description": physical_description,
            "Clothing and Accessories": self._build_clothing_block(case),
            "Physical Features": physical_features,
            "Eye Color": physical_description.get("Eye Color", ""),
            "Hair Color": physical_description.get("Hair Color", ""),
            "Physical Features Summary": self._physical_features_summary(physical_features),
            "Circumstances": self._build_circumstances_block(case),
            "Investigating Agencies": agency_names,
            "Investigating Agencies Summary": self._summarize_names(agency_names),
            "Media": self._build_media_block(case),
            "Vehicles Count": len(case.get("vehicles") or []),
            "Top Level Keys": sorted(case.keys()),
        }

    def _prune_parsed_blobs(self, case: Dict[str, Any]) -> None:
        for key in self.PRUNED_PARSED_BLOBS:
            case.pop(key, None)

