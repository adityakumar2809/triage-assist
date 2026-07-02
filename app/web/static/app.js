(() => {
  const setupIntakeEnhancements = () => {
    const searchInput = document.querySelector("[data-symptom-search]");
    const filterInput = document.querySelector("[data-symptom-filter]");
    const addButton = document.querySelector("[data-add-symptom]");
    const selectedCount = document.querySelector("[data-selected-count]");
    const selectedChips = document.querySelector("[data-selected-chips]");
    const checkboxes = Array.from(
      document.querySelectorAll("[data-symptom-checkbox]")
    );
    const groups = Array.from(
      document.querySelectorAll("[data-body-group]")
    );

    if (
      !searchInput ||
      !filterInput ||
      !addButton ||
      !selectedCount ||
      !selectedChips ||
      !checkboxes.length
    ) {
      return;
    }

    const checkboxByCanonical = new Map();
    const checkboxByHumanized = new Map();
    const labelByCanonical = new Map();

    checkboxes.forEach((checkbox) => {
      const label = checkbox.closest("[data-symptom-label]");
      if (!label) {
        return;
      }
      const canonicalName = checkbox.value;
      const humanizedName = String(label.dataset.symptomHumanized || "");
      checkboxByCanonical.set(canonicalName.toLowerCase(), checkbox);
      checkboxByHumanized.set(humanizedName.toLowerCase(), checkbox);
      labelByCanonical.set(canonicalName, label);
    });

    const updateSelectedSummary = () => {
      const selected = checkboxes.filter((checkbox) => checkbox.checked);
      selectedCount.textContent = String(selected.length);
      selectedChips.innerHTML = "";

      selected.forEach((checkbox) => {
        const label = labelByCanonical.get(checkbox.value);
        if (!label) {
          return;
        }

        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = label.dataset.symptomHumanized || checkbox.value;

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.textContent = "×";
        removeButton.setAttribute(
          "aria-label",
          `Remove ${chip.textContent}`
        );
        removeButton.addEventListener("click", () => {
          checkbox.checked = false;
          checkbox.dispatchEvent(new Event("change", { bubbles: true }));
        });

        chip.appendChild(removeButton);
        selectedChips.appendChild(chip);
      });
    };

    const addFromSearch = () => {
      const rawValue = searchInput.value.trim().toLowerCase();
      if (!rawValue) {
        return;
      }
      const checkbox =
        checkboxByCanonical.get(rawValue) ||
        checkboxByHumanized.get(rawValue);
      if (!checkbox) {
        return;
      }
      checkbox.checked = true;
      checkbox.dispatchEvent(new Event("change", { bubbles: true }));
      const label = labelByCanonical.get(checkbox.value);
      if (label) {
        label.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      searchInput.value = "";
    };

    const applyFilter = () => {
      const query = filterInput.value.trim().toLowerCase();
      groups.forEach((group) => {
        const labels = Array.from(
          group.querySelectorAll("[data-symptom-label]")
        );
        let visibleCount = 0;
        labels.forEach((label) => {
          const canonical = String(
            label.dataset.symptomName || ""
          ).toLowerCase();
          const humanized = String(
            label.dataset.symptomHumanized || ""
          ).toLowerCase();
          const isMatch =
            !query || canonical.includes(query) || humanized.includes(query);
          label.dataset.hidden = isMatch ? "false" : "true";
          if (isMatch) {
            visibleCount += 1;
          }
        });

        if (!query) {
          group.open = false;
          group.hidden = false;
          return;
        }
        group.open = visibleCount > 0;
        group.hidden = visibleCount === 0;
      });
    };

    addButton.addEventListener("click", addFromSearch);
    searchInput.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") {
        return;
      }
      event.preventDefault();
      addFromSearch();
    });
    filterInput.addEventListener("input", applyFilter);
    checkboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", updateSelectedSummary);
    });

    updateSelectedSummary();
    applyFilter();
  };

  const setupIntakeFormBehavior = () => {
    const form = document.querySelector("[data-intake-form]");
    if (!form) {
      return;
    }

    const rawTextInput = form.querySelector("[data-raw-text]");
    const submitButton = form.querySelector("[data-submit-button]");
    const validationError = form.querySelector("[data-validation-error]");
    const symptomCheckboxes = Array.from(
      form.querySelectorAll("[data-symptom-checkbox]")
    );
    const severitySlider = form.querySelector("[data-severity-slider]");
    const severityValue = form.querySelector("#self_severity_1_10");
    const severityOutput = form.querySelector("#severity_value_hint");

    const hideValidationError = () => {
      if (validationError) {
        validationError.hidden = true;
      }
    };

    const syncSubmitLabel = () => {
      if (!rawTextInput || !submitButton) {
        return;
      }
      const hasRawText = rawTextInput.value.trim().length > 0;
      submitButton.textContent = hasRawText
        ? "Review mapped symptoms"
        : "Submit symptoms";
    };

    const syncSeverity = () => {
      if (!severitySlider) {
        return;
      }
      if (severityOutput) {
        severityOutput.textContent = severitySlider.value;
      }
      if (severityValue) {
        severityValue.value = severitySlider.value;
      }
    };

    if (rawTextInput) {
      rawTextInput.addEventListener("input", () => {
        syncSubmitLabel();
        hideValidationError();
      });
    }

    symptomCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", hideValidationError);
    });

    if (severitySlider) {
      severitySlider.addEventListener("input", syncSeverity);
    }

    syncSubmitLabel();

    form.addEventListener("submit", (event) => {
      const hasSymptomSelected = symptomCheckboxes.some(
        (checkbox) => checkbox.checked
      );
      const hasRawText = rawTextInput
        ? rawTextInput.value.trim().length > 0
        : false;
      if (hasSymptomSelected || hasRawText) {
        hideValidationError();
        return;
      }
      event.preventDefault();
      if (validationError) {
        validationError.hidden = false;
      }
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    setupIntakeEnhancements();
    setupIntakeFormBehavior();
  });
})();
