# FormFit Country System

Added country-first onboarding before login. Preferences are saved in localStorage under `formfit_country_preferences_v1` and exposed as `window.FormFitCountry`. Dashboard account sheet includes Change country. Existing pose/camera/form-checker files were not modified.

Current country data includes a broad worldwide list with locale, weight unit and height unit defaults. Diet/exercise engines can consume `window.FormFitCountry` or the `formfit:country-changed` event in future backend work.
