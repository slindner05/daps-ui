// TODO: add info hover tip for schedules
document.addEventListener("DOMContentLoaded", function () {
  createNavExtension();
  attachNewInstance("radarr");
  attachNewInstance("sonarr");
  attachNewInstance("plex");
  attachPosterRenamer();
  attachLogLevel();
  attachUnmatchedAssets();
  attachPlexUploaderr();
  attachDriveSync();

  fetch("/get-settings")
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        preFillForm(data.settings);
        console.log(data.settings);
        captureInitialState();
        attachInputListeners();
      } else {
        console.error("Error fetching settings: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error", error);
    });

  const sourceList = document.getElementById("source_dir_div");
  const settingsContainer = document.getElementById("settings-container");
  initializeDragAndDrop(sourceList);
  const observer = new MutationObserver((mutationList) => {
    mutationList.forEach((mutation) => {
      if (mutation.type === "childList" && mutation.addedNodes.length > 0) {
        mutation.addedNodes.forEach((node) => {
          if (node.matches?.("input, select, textarea")) {
            attachInputListener(node);
          }
        });
        mutation.removedNodes.forEach(() => {
          checkChanges();
        });
      }
    });
    attachInputListeners();
    checkChanges();
  });
  observer.observe(settingsContainer, {
    childList: true,
    subtree: true,
  });
});

let initialState = [];

function attachInputListeners() {
  const inputs = document.querySelectorAll("input, select, textarea");
  inputs.forEach((input) => {
    input.addEventListener("input", checkChanges);
    input.addEventListener("change", checkChanges);
  });
}
function attachInputListener(input) {
  input.addEventListener("input", checkChanges);
  input.addEventListener("change", checkChanges);
}

function captureInitialState() {
  const inputs = document.querySelectorAll("input, select, textarea");
  initialState = Array.from(inputs).map((input) => {
    if (input.type === "checkbox" || input.type === "radio") {
      return input.checked;
    }
    return input.value;
  });
  console.log("Initial state captured:", initialState);
}

function checkChanges() {
  const inputs = Array.from(
    document.querySelectorAll("input, select, textarea"),
  );
  const curentStates = inputs.map((input) => {
    if (input.type === "checkbox" || input.type === "radio") {
      return input.checked;
    }
    return input.value;
  });

  const initialStateReverted =
    initialState.length === curentStates.length &&
    initialState.every((state, index) => state === curentStates[index]);
  if (initialStateReverted) {
    disableSaveButton();
  } else {
    enableSaveButton();
  }
}
function enableSaveButton() {
  const saveButton = document.getElementById("save-settings");
  saveButton.disabled = false;
  saveButton.classList.add("enabled");
  const saveText = saveButton.querySelector("span");
  if (saveText) {
    saveText.textContent = "Save Changes";
  }
}
function disableSaveButton() {
  const saveButton = document.getElementById("save-settings");
  saveButton.disabled = true;
  saveButton.classList.remove("enabled");
  const saveText = saveButton.querySelector("span");
  if (saveText) {
    saveText.textContent = "No Changes";
  }
}

function createNavExtension() {
  const layoutContainer = document.getElementById("layout-wrapper");
  const navExtension = document.createElement("div");
  navExtension.classList.add("nav-extension");
  layoutContainer.appendChild(navExtension);

  const saveButton = document.createElement("button");
  saveButton.id = "save-settings";
  saveButton.classList.add("save-button");

  const saveIcon = document.createElement("i");
  saveIcon.classList.add("fa", "fa-save");
  saveButton.appendChild(saveIcon);

  const saveText = document.createElement("span");
  saveText.textContent = "No Changes";
  saveText.classList.add("save-text");
  saveButton.appendChild(saveText);
  saveButton.disabled = true;

  attachSaveSettingsListener(saveButton);

  navExtension.appendChild(saveButton);
}
function toggleCustomColorInput() {
  const borderColorSelect = document.getElementById("border_select");
  const customColorInput = document.getElementById("custom_color");
  const customColorLabel = document.querySelector('label[for="hex_code"]');

  if (borderColorSelect.value === "custom") {
    customColorLabel.style.display = "inline-block";
    customColorInput.style.display = "inline-block";
  } else {
    customColorLabel.style.display = "none";
    customColorInput.style.display = "none";
  }

  borderColorSelect.addEventListener("change", (event) => {
    if (event.target.value === "custom") {
      customColorLabel.style.display = "inline-block";
      customColorInput.style.display = "inline-block";
    } else {
      customColorLabel.style.display = "none";
      customColorInput.style.display = "none";
    }
  });
}

function initializeDragAndDrop(container) {
  container.addEventListener("dragstart", handleDragStart);
  container.addEventListener("dragend", handleDragEnd);
  container.addEventListener("dragover", handleDragOver);
}

function handleDragStart(e) {
  if (e.target.classList.contains("source-item")) {
    e.target.classList.add("dragging");
  }
}

function handleDragEnd(e) {
  e.target.classList.remove("dragging");
  renameItemIds();
}

function handleDragOver(e) {
  e.preventDefault();
  const container = e.currentTarget;
  const afterElement = getDragAfterElement(container, e.clientY);
  const draggingItem = document.querySelector(".dragging");
  if (afterElement == null) {
    container.appendChild(draggingItem);
  } else {
    container.insertBefore(draggingItem, afterElement);
  }
}

function getDragAfterElement(container, y) {
  const draggableElements = [
    ...container.querySelectorAll(".source-item:not(.dragging)"),
  ];
  return draggableElements.reduce(
    (closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset: offset, element: child };
      } else {
        return closest;
      }
    },
    { offset: Number.NEGATIVE_INFINITY },
  ).element;
}
function renameItemIds() {
  const items = document.querySelectorAll(".source-item");
  items.forEach((item, index) => {
    item.id = `source_dir_${index + 1}`;
  });
}

function createInstanceFromSettings(data, settingsVar, htmlVar) {
  for (let i = 1; i < data[settingsVar].length; i++) {
    attachNewInstance(htmlVar);
  }
  const instanceInputs = document.querySelectorAll(
    `input[name="${htmlVar}_instance[]"]`,
  );
  const urlInputs = document.querySelectorAll(`input[name="${htmlVar}_url[]"]`);
  const apiInputs = document.querySelectorAll(`input[name="${htmlVar}_api[]"]`);

  instanceInputs.forEach((input, index) => {
    input.value = data[settingsVar][index]?.instanceName || "";
  });
  urlInputs.forEach((input, index) => {
    input.value = data[settingsVar][index]?.url || "";
  });
  apiInputs.forEach((input, index) => {
    input.value = data[settingsVar][index]?.apiKey || "";
  });
}
function createInputFromSettings(data, settingsVar, htmlVar) {
  for (let i = 1; i < data[settingsVar].length; i++) {
    createAdditionalInput(htmlVar, placeholders[settingsVar]);
  }
  const dynamicInput = document.querySelectorAll(`input[name="${htmlVar}[]"]`);
  dynamicInput.forEach((input, index) => {
    input.value = data[settingsVar][index] || "";
  });
}

function createDriveFromSettings(data) {
  const driveSelectDiv = document.querySelector(".drive-select-div");
  const driveSelectWrappers = driveSelectDiv.querySelectorAll(
    ".drive-select-wrapper",
  );

  data["gdrives"].forEach((gdrive, index) => {
    let driveSelectWrapper;

    if (index === 0 && driveSelectWrappers.length > 0) {
      driveSelectWrapper = driveSelectWrappers[0];
    } else {
      driveSelectWrapper = createDriveSelect(driveSelectCounter);
      driveSelectDiv.appendChild(driveSelectWrapper);
      driveSelectCounter++;
    }

    const selectElement = driveSelectWrapper.querySelector(
      "select[name='gdrive-select']",
    );
    const locationInput = driveSelectWrapper.querySelector(
      "input[name='gdrive-location']",
    );
    const customInput = driveSelectWrapper.querySelector(
      "input[name='custom-drive-id']",
    );
    if (locationInput) {
      locationInput.value = gdrive.location || "";
    }
    if (selectElement) {
      const optionExists = Array.from(selectElement.options).some(
        (option) => option.value === gdrive.id,
      );
      if (optionExists) {
        selectElement.value = gdrive.id;
      } else {
        selectElement.value = "custom";
        customInput.style.display = "block";
        customInput.value = gdrive.id;
        selectElement.style.display = "none";
      }
    }
  });

  if (driveSelectCounter >= 1) {
    driveSelectWrappers.forEach((wrapper) => {
      const removeButton = wrapper.querySelector(".close");
      if (removeButton) {
        removeButton.style.display = "inline";
      }
    });
  }
}

function preFillForm(data) {
  document.querySelector('input[name="target_path"]').value =
    data.targetPath || "";
  document.querySelector('input[name="poster_renamer_schedule"]').value =
    data.posterRenamerSchedule || "";
  document.querySelector('input[name="unmatched_assets_schedule"]').value =
    data.unmatchedAssetsSchedule || "";
  document.querySelector('input[name="plex_uploaderr_schedule"]').value =
    data.plexUploaderrSchedule || "";
  document.getElementById("poster-renamer_info").checked = true;
  document.getElementById("unmatched-assets_info").checked = true;
  document.getElementById("plex-uploaderr_info").checked = true;
  document.getElementById("border-replacerr_info").checked = true;

  if (data.logLevelPosterRenamer === "debug") {
    document.getElementById("poster-renamer_info").checked = false;
    document.getElementById("poster-renamer_debug").checked = true;
  }
  if (data.logLevelUnmatchedAssets === "debug") {
    document.getElementById("unmatched-assets_info").checked = false;
    document.getElementById("unmatched-assets_debug").checked = true;
  }
  if (data.logLevelPlexUploaderr === "debug") {
    document.getElementById("plex-uploaderr_info").checked = false;
    document.getElementById("plex-uploaderr_debug").checked = true;
  }
  if (data.logLevelBorderReplacerr === "debug") {
    document.getElementById("border-replacerr_info").checked = false;
    document.getElementById("border-replacerr_debug").checked = true;
  }

  createInputFromSettings(data, "sourceDirs", "source_dir");
  createInputFromSettings(data, "libraryNames", "library_name");
  createInputFromSettings(data, "instances", "instance");
  document.getElementById("asset_folders").checked = data.assetFolders || false;
  document.getElementById("clean_assets").checked = data.cleanAssets || false;
  document.getElementById("match_alt").checked = data.matchAlt || false;
  document.getElementById("replace_border").checked =
    data.replaceBorder || false;
  document.getElementById("unmatched_assets").checked =
    data.unmatchedAssets || false;
  document.getElementById("run_single_item").checked =
    data.runSingleItem || false;
  document.getElementById("only_unmatched").checked =
    data.onlyUnmatched || false;
  document.getElementById("upload_to_plex").checked =
    data.uploadToPlex || false;
  document.getElementById("reapply_posters").checked =
    data.reapplyPosters || false;
  document.getElementById("show_all_unmatched").checked =
    data.showAllUnmatched || false;
  document.getElementById("disable_unmatched_collections").checked =
    data.disableUnmatchedCollections || false;

  createInstanceFromSettings(data, "radarrInstances", "radarr");
  createInstanceFromSettings(data, "sonarrInstances", "sonarr");
  createInstanceFromSettings(data, "plexInstances", "plex");
  document.getElementById("rclone-client-id").value = data.client_id || "";
  document.getElementById("rclone-token").value = data.rclone_token || "";
  document.getElementById("rclone-secret").value = data.rclone_secret || "";
  document.getElementById("sa-location").value = data.sa_location || "";

  createDriveFromSettings(data);

  if (data.borderSetting) {
    const borderColorSelect = document.querySelector(
      'select[name="border_setting"]',
    );
    if (borderColorSelect) {
      borderColorSelect.value = data.borderSetting;
    }
  }
  attachReplaceBorderToggle();
  toggleCustomColorInput();
  document.querySelector('input[name="hex_code"]').value =
    data.customColor || "";
}

function attachPosterRenamer() {
  const wrapperDiv = document.getElementById("poster-renamer-form");
  const formGroup = createPosterRenamer();
  wrapperDiv.appendChild(formGroup);
}
function attachLogLevel() {
  const wrapperDiv = document.getElementById("log-level-wrapper");
  const posterRenamerLogLevel = createLogLevelGroup(
    "Poster Renamerr",
    "poster-renamer",
  );
  const unmatchedAssetsLogLevel = createLogLevelGroup(
    "Unmatched Assets",
    "unmatched-assets",
  );
  const plexUploaderrLogLevel = createLogLevelGroup(
    "Plex Uploaderr",
    "plex-uploaderr",
  );
  const borderReplacerrLogLevel = createLogLevelGroup(
    "Border Replacerr",
    "border-replacerr",
  );

  wrapperDiv.appendChild(posterRenamerLogLevel);
  wrapperDiv.appendChild(unmatchedAssetsLogLevel);
  wrapperDiv.appendChild(plexUploaderrLogLevel);
  wrapperDiv.appendChild(borderReplacerrLogLevel);
}
function attachUnmatchedAssets() {
  const wrapperDiv = document.getElementById("unmatched-assets-wrapper");
  const unmatchedAssets = createUnmatchedAssets();
  wrapperDiv.appendChild(unmatchedAssets);
}
function attachPlexUploaderr() {
  const wrapperDiv = document.getElementById("plex-uploaderr-wrapper");
  const plexUploaderr = createPlexUploaderr();
  wrapperDiv.appendChild(plexUploaderr);
}
function attachDriveSync() {
  const wrapperDiv = document.getElementById("drive-sync-wrapper");
  const driveSync = createDriveSync();
  wrapperDiv.appendChild(driveSync);
}

function createLabel(labelName, inputName) {
  const label = document.createElement("label");
  label.classList.add("form-label");
  label.setAttribute("for", `${inputName}`);
  label.textContent = `${labelName}`;
  return label;
}

function createInput(inputType, placeholder) {
  const input = document.createElement("input");
  input.type = "text";
  input.name = `${inputType}[]`;
  input.placeholder = placeholder;
  input.classList.add("form-input");
  return input;
}
function createInputDiv(inputType, input) {
  const wrapperDiv = document.createElement("div");
  wrapperDiv.classList.add("input-div-group");
  wrapperDiv.id = `${inputType}_${inputCounters[inputType]}`;

  if (inputType === "source_dir") {
    const dragHandle = document.createElement("span");
    dragHandle.classList.add("drag-handle");
    dragHandle.textContent = "☰";
    wrapperDiv.appendChild(dragHandle);
  }

  const removeButton = document.createElement("button");
  if (inputCounters[inputType] === 1) {
    removeButton.style.display = "none";
  }
  removeButton.classList.add("btn", "btn-primary", "btn-remove");
  removeButton.type = "button";

  const trashIcon = document.createElement("i");
  trashIcon.classList.add("fas", "fa-trash-alt");

  removeButton.appendChild(trashIcon);
  wrapperDiv.appendChild(input);
  wrapperDiv.appendChild(removeButton);

  return wrapperDiv;
}

function createCheckboxInput(labelName, inputId, name = null, value = null) {
  const div = document.createElement("div");
  div.classList.add("checkbox-container");

  const label = document.createElement("label");
  label.classList.add("custom-checkbox-label");

  const text = document.createElement("span");
  text.textContent = labelName;
  text.classList.add("form-label");

  const input = document.createElement("input");
  input.type = "checkbox";
  input.id = inputId;
  input.name = name;
  input.value = value;
  input.classList.add("custom-checkbox");

  const span = document.createElement("span");
  span.classList.add("slider");

  // const icon = document.createElement("i");
  // icon.classList.add("fas", "fa-check");

  label.appendChild(text);
  label.appendChild(input);
  label.appendChild(span);
  div.appendChild(label);

  return div;
}
function attachReplaceBorderToggle() {
  const borderReplacerCheckbox = document.getElementById("replace_border");
  const borderColorDiv = document.getElementById("border_color_div");
  function toggleBorderColorDiv() {
    if (borderReplacerCheckbox.checked) {
      borderColorDiv.style.display = "block";
    } else {
      borderColorDiv.style.display = "none";
    }
  }
  borderReplacerCheckbox.addEventListener("change", toggleBorderColorDiv);
  toggleBorderColorDiv();
}

function createAddButton(name, text) {
  const addButton = document.createElement("button");
  addButton.classList.add("btn", "btn-primary", "btn-add");
  addButton.type = "button";
  addButton.id = `add_input_${name}`;

  const plusIcon = document.createElement("i");
  plusIcon.classList.add("fa", "fa-plus");
  addButton.appendChild(plusIcon);
  const textNode = document.createTextNode(` ${text}`);
  addButton.appendChild(textNode);
  return addButton;
}

let inputCounters = {
  source_dir: 1,
  library_name: 1,
  instance: 1,
};

let placeholders = {
  targetPath: "/kometa/assets",
  sourceDir: "/posters/Drazzilb08",
  libraryName: "Movies (HD)",
  instance: "radarr_1",
  cronSchedule: "cron(0 */3 * * *)",
};

function createAdditionalInput(inputType, placeholder) {
  inputCounters[inputType]++;
  const wrapperDiv = document.getElementById(`${inputType}_div`);
  const buttons = wrapperDiv.querySelectorAll(".btn-remove");
  if (inputCounters[inputType] > 1) {
    buttons.forEach((button) => {
      button.style.display = "block";
    });
  }
  const input = createInput(inputType, placeholder);
  const inputDiv = createInputDiv(inputType, input);
  if (inputType === "source_dir") {
    inputDiv.classList.add("source-item");
    inputDiv.setAttribute("draggable", "true");
  }
  const removeButton = inputDiv.querySelector("button");
  attachRemoveButtonListener(wrapperDiv, inputType, removeButton);
  wrapperDiv.appendChild(inputDiv);
}

function attachRemoveButtonListener(wrapperDiv, inputType, removeButton) {
  removeButton.addEventListener("click", function () {
    inputCounters[inputType]--;
    const parentElement = removeButton.parentElement;
    parentElement.remove();
    const buttons = wrapperDiv.querySelectorAll(".btn-remove");
    if (inputCounters[inputType] === 1) {
      buttons.forEach((button) => {
        button.style.display = "none";
      });
    }
    updateinputDivId(wrapperDiv, inputType);
  });
}
function updateinputDivId(wrapperDiv, inputType) {
  const inputDivs = wrapperDiv.querySelectorAll(".input-div-group");
  inputDivs.forEach((inputDiv, index) => {
    inputDiv.id = `${inputType}_${index + 1}`;
  });
}

function attachAddButtonListener(button, inputType, placeholder) {
  button.addEventListener("click", function () {
    createAdditionalInput(inputType, placeholder);
  });
}
function createPosterRenamer() {
  const formGroup = document.createElement("div");
  const buttonDiv = document.createElement("div");
  buttonDiv.id = "button_div";
  buttonDiv.classList.add("button-div");
  const sourceDirsDiv = document.createElement("div");
  sourceDirsDiv.id = "source_dir_div";
  const instancesDiv = document.createElement("div");
  instancesDiv.id = "instance_div";
  const libraryNamesDiv = document.createElement("div");
  libraryNamesDiv.id = "library_name_div";
  const borderColorDiv = document.createElement("div");
  borderColorDiv.id = "border_color_div";
  borderColorDiv.classList.add("border-color-div");
  const checkboxDiv = document.createElement("div");
  checkboxDiv.classList.add("form-group-checkbox");

  const cronScheduleInput = document.createElement("input");
  cronScheduleInput.name = "poster_renamer_schedule";
  cronScheduleInput.type = "text";
  cronScheduleInput.classList.add("form-input");
  cronScheduleInput.placeholder = placeholders["cronSchedule"];
  const cronScheduleLabel = createLabel(
    "Schedule",
    `${cronScheduleInput.name}`,
  );
  cronScheduleLabel.appendChild(cronScheduleInput);

  const targetPathInput = document.createElement("input");
  targetPathInput.name = "target_path";
  targetPathInput.type = "text";
  targetPathInput.classList.add("form-input");
  targetPathInput.placeholder = placeholders["targetPath"];
  const targetPathLabel = createLabel("Target Path", `${targetPathInput.name}`);
  targetPathLabel.appendChild(targetPathInput);

  const sourceDirInput = createInput("source_dir", placeholders["sourceDir"]);
  const sourceDirLabel = createLabel(
    "Source Directories",
    `${sourceDirInput.name}`,
  );
  const sourceDirInputDiv = createInputDiv("source_dir", sourceDirInput);
  sourceDirInputDiv.classList.add("source-item");
  sourceDirInputDiv.setAttribute("draggable", "true");
  const sourceDirRemoveButton = sourceDirInputDiv.querySelector(".btn-remove");
  attachRemoveButtonListener(
    sourceDirsDiv,
    "source_dir",
    sourceDirRemoveButton,
  );

  const libraryNameInput = createInput(
    "library_name",
    placeholders["libraryName"],
  );
  const libraryNamesLabel = createLabel(
    "Library Names",
    `${libraryNameInput.name}`,
  );
  const libraryNameInputDiv = createInputDiv("library_name", libraryNameInput);
  const libraryNameRemoveButton =
    libraryNameInputDiv.querySelector(".btn-remove");
  attachRemoveButtonListener(
    libraryNamesDiv,
    "library_name",
    libraryNameRemoveButton,
  );

  const instanceInput = createInput("instance", placeholders["instance"]);
  const instanceLabel = createLabel("Instances", `${instanceInput.name}`);
  const instanceInputDiv = createInputDiv("instance", instanceInput);
  const instanceRemoveButton = instanceInputDiv.querySelector(".btn-remove");
  attachRemoveButtonListener(instancesDiv, "instance", instanceRemoveButton);

  const supportedColors = ["remove", "black", "custom"];

  const borderColorSelect = document.createElement("select");
  borderColorSelect.id = "border_select";
  borderColorSelect.name = "border_setting";
  borderColorSelect.classList.add("form-select");
  supportedColors.forEach((color) => {
    const option = document.createElement("option");
    option.value = color;
    option.textContent = color.charAt(0).toUpperCase() + color.slice(1);
    borderColorSelect.appendChild(option);
  });

  const customColorInput = document.createElement("input");
  customColorInput.id = "custom_color";
  customColorInput.name = "hex_code";
  customColorInput.type = "text";
  customColorInput.classList.add("form-input");
  customColorInput.placeholder = "#FFFFFF";
  customColorInput.style.display = "none";
  customColorInput.maxLength = 7;
  const customColorLabel = createLabel("Hex Code", `${customColorInput.name}`);
  customColorLabel.style.display = "none";

  const borderColorLabel = createLabel("Border Color", "border_setting");

  const assetFoldersCheckbox = createCheckboxInput(
    "Asset Folders",
    "asset_folders",
  );
  const cleanPosters = createCheckboxInput("Clean Assets", "clean_assets");

  const borderReplacerCheckbox = createCheckboxInput(
    "Replace Border",
    "replace_border",
  );
  const unmatchedAssetsCheckbox = createCheckboxInput(
    "Unmatched Assets",
    "unmatched_assets",
  );

  const runSingleItemCheckbox = createCheckboxInput(
    "Webhook Run",
    "run_single_item",
  );
  const uploadToPlex = createCheckboxInput("Plex Upload", "upload_to_plex");
  const matchAltCheckbox = createCheckboxInput("Match Alt Titles", "match_alt");
  const onlyUnmatched = createCheckboxInput("Only Unmatched", "only_unmatched");

  const addSourceDirButton = createAddButton("source_dir", "Add Source Dir");
  attachAddButtonListener(
    addSourceDirButton,
    "source_dir",
    placeholders["sourceDir"],
  );
  const addLibraryNamesButton = createAddButton("library_name", "Add Library");
  attachAddButtonListener(
    addLibraryNamesButton,
    "library_name",
    placeholders["libraryName"],
  );
  const addInstancesButton = createAddButton("instances", "Add Instance");
  attachAddButtonListener(
    addInstancesButton,
    "instance",
    placeholders["instance"],
  );
  buttonDiv.appendChild(addSourceDirButton);
  buttonDiv.appendChild(addLibraryNamesButton);
  buttonDiv.appendChild(addInstancesButton);

  sourceDirsDiv.appendChild(sourceDirLabel);
  sourceDirsDiv.appendChild(sourceDirInputDiv);

  libraryNamesDiv.appendChild(libraryNamesLabel);
  libraryNamesDiv.appendChild(libraryNameInputDiv);

  instancesDiv.appendChild(instanceLabel);
  instancesDiv.appendChild(instanceInputDiv);
  borderColorDiv.appendChild(borderColorLabel);
  borderColorDiv.appendChild(borderColorSelect);
  borderColorDiv.appendChild(customColorLabel);
  borderColorDiv.appendChild(customColorInput);

  checkboxDiv.appendChild(assetFoldersCheckbox);
  checkboxDiv.appendChild(cleanPosters);
  checkboxDiv.appendChild(borderReplacerCheckbox);
  checkboxDiv.appendChild(unmatchedAssetsCheckbox);
  checkboxDiv.appendChild(runSingleItemCheckbox);
  checkboxDiv.appendChild(onlyUnmatched);
  checkboxDiv.appendChild(uploadToPlex);
  checkboxDiv.appendChild(matchAltCheckbox);

  // formGroup.appendChild(logLevelLabel);
  formGroup.appendChild(cronScheduleLabel);
  formGroup.appendChild(targetPathLabel);
  formGroup.appendChild(sourceDirsDiv);
  formGroup.appendChild(libraryNamesDiv);
  formGroup.appendChild(instancesDiv);
  formGroup.appendChild(borderColorDiv);
  formGroup.appendChild(checkboxDiv);
  formGroup.appendChild(buttonDiv);

  return formGroup;
}

let counters = {
  sonarr: 0,
  radarr: 0,
  plex: 0,
};

function createUnmatchedAssets() {
  const wrapperDiv = document.createElement("div");
  const checkboxDiv = document.createElement("div");
  checkboxDiv.classList.add("form-group-checkbox");

  const cronScheduleInput = document.createElement("input");
  cronScheduleInput.name = "unmatched_assets_schedule";
  cronScheduleInput.type = "text";
  cronScheduleInput.classList.add("form-input");
  cronScheduleInput.placeholder = placeholders["cronSchedule"];
  const cronScheduleLabel = createLabel(
    "Schedule",
    `${cronScheduleInput.name}`,
  );
  cronScheduleLabel.appendChild(cronScheduleInput);

  const showAllCheckbox = createCheckboxInput(
    "Show all unmatched",
    "show_all_unmatched",
  );
  const disableUnmatchedCollections = createCheckboxInput(
    "Hide Collections",
    "disable_unmatched_collections",
  );
  checkboxDiv.appendChild(showAllCheckbox);
  checkboxDiv.appendChild(disableUnmatchedCollections);

  wrapperDiv.appendChild(cronScheduleLabel);
  wrapperDiv.appendChild(checkboxDiv);
  return wrapperDiv;
}

function createPlexUploaderr() {
  const wrapperDiv = document.createElement("div");
  const checkboxDiv = document.createElement("div");
  checkboxDiv.classList.add("form-group-checkbox");

  const cronScheduleInput = document.createElement("input");
  cronScheduleInput.name = "plex_uploaderr_schedule";
  cronScheduleInput.type = "text";
  cronScheduleInput.classList.add("form-input");
  cronScheduleInput.placeholder = placeholders["cronSchedule"];
  const cronScheduleLabel = createLabel(
    "Schedule",
    `${cronScheduleInput.name}`,
  );
  cronScheduleLabel.appendChild(cronScheduleInput);

  const reapplyPosters = createCheckboxInput(
    "Reapply Posters",
    "reapply_posters",
  );
  checkboxDiv.appendChild(reapplyPosters);

  wrapperDiv.appendChild(cronScheduleLabel);
  wrapperDiv.appendChild(checkboxDiv);
  return wrapperDiv;
}

let driveSelectCounter = 0;

let availableDrives = {
  drazzilb: "1VeeQ_frBFpp6AZLimaJSSr0Qsrl6Tb7z",
  dsaq: "1wrSru-46iIN1iqCl2Cjhj5ofdazPgbsz",
  zarox: "1wOhY88zc0wdQU-QQmhm4FzHL9QiCQnpu",
  solen: "1YEuS1pulJAfhKm4L8U9z5-EMtGl-d2s7",
  bz: "1Xg9Huh7THDbmjeanW0KyRbEm6mGn_jm8",
  chrisdc: "1oBzEOXXrTHGq6sUY_4RMtzMTt4VHyeJp",
  quafley: "1G77TLQvgs_R7HdMWkMcwHL6vd_96cMp7",
  stupifier: "1bBbK_3JeXCy3ElqTwkFHaNoNxYgqtLug",
  sahara: "1KnwxzwBUQzQyKF1e24q_wlFqcER9xYHM",
  lion: "1alseEnUBjH6CjXh77b5L4R-ZDGdtOMFr",
  majorgiant: "1ZfvUgN0qz4lJYkC_iMRjhH-fZ0rDN_Yu",
  iamspartacus: "1aRngLdC9yO93gvSrTI2LQ_I9BSoGD-7o",
  mareau: "1hEY9qEdXVDzIbnQ4z9Vpo0SVXXuZBZR",
  solen_collection: "1zWY-ORtJkOLcQChV--oHquxW3JCow1zm",
  majorgiant_collection: "15sNlcFZmeDox2OQJyGjVxRwtigtd82Ru",
  iamspartacus_collection: "1-WhCVwRLfV6hxyKF7W5IuzIHIYicCdAv",
};

function createDriveSync() {
  const wrapperDiv = document.createElement("div");

  const cronScheduleInput = document.createElement("input");
  cronScheduleInput.id = "drive-sync-schedule";
  cronScheduleInput.type = "text";
  cronScheduleInput.classList.add("form-input");
  cronScheduleInput.placeholder = placeholders["cronSchedule"];
  const cronScheduleLabel = createLabel("Schedule", `${cronScheduleInput.id}`);

  const driveSelectDiv = document.createElement("div");
  driveSelectDiv.classList.add("drive-select-div");

  const driveLabel = document.createElement("label");
  driveLabel.textContent = "G-Drives";
  driveLabel.classList.add("form-label");

  const firstDriveSelect = createDriveSelect(driveSelectCounter);
  driveSelectCounter++;
  driveSelectDiv.appendChild(firstDriveSelect);

  const buttonDiv = document.createElement("div");
  buttonDiv.classList.add("button-div");

  const configureButton = document.createElement("button");
  configureButton.id = "configure-drive-sync";
  configureButton.type = "button";
  configureButton.classList.add("btn", "btn-primary");
  configureButton.textContent = "Configure";
  buttonDiv.appendChild(configureButton);

  const addDriveButton = document.createElement("button");
  addDriveButton.id = "add-drive-button";
  addDriveButton.type = "button";
  addDriveButton.classList.add("btn", "btn-primary");
  addDriveButton.textContent = "+ Add GDrive";
  buttonDiv.appendChild(addDriveButton);

  wrapperDiv.appendChild(cronScheduleLabel);
  wrapperDiv.appendChild(cronScheduleInput);
  wrapperDiv.appendChild(driveLabel);
  wrapperDiv.appendChild(driveSelectDiv);
  wrapperDiv.appendChild(buttonDiv);

  const modal = createModal();
  wrapperDiv.appendChild(modal);

  configureButton.addEventListener("click", () => {
    modal.style.display = "block";
  });

  addDriveButton.addEventListener("click", () => {
    const dynamicSelect = createDriveSelect(driveSelectCounter);
    driveSelectDiv.appendChild(dynamicSelect);
    if (driveSelectCounter >= 1) {
      const firstDriveSelect = driveSelectDiv.querySelector(
        ".drive-select-wrapper[data-counter='0']",
      );
      if (firstDriveSelect) {
        const firstRemoveButton = firstDriveSelect.querySelector(".close");
        firstRemoveButton.style.display = "inline";
      }
    }
    driveSelectCounter++;
  });

  return wrapperDiv;
}

function createDriveSelect(counter) {
  const selectWrapper = document.createElement("div");
  selectWrapper.classList.add("drive-select-wrapper");
  selectWrapper.dataset.counter = counter;

  const selectElement = document.createElement("select");
  selectElement.classList.add("form-select");
  selectElement.name = "gdrive-select";

  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "Select a drive...";
  defaultOption.selected = true;
  defaultOption.disabled = true;
  selectElement.appendChild(defaultOption);

  Object.entries(availableDrives).forEach(([name, id]) => {
    const optionElement = document.createElement("option");
    optionElement.value = id;
    optionElement.textContent = name;
    selectElement.appendChild(optionElement);
  });

  const customDrive = document.createElement("option");
  customDrive.value = "custom";
  customDrive.textContent = "Custom Drive ID...";
  selectElement.appendChild(customDrive);

  const customDriveInput = document.createElement("input");
  customDriveInput.classList.add("form-input");
  customDriveInput.name = "custom-drive-id";
  customDriveInput.placeholder = "Enter GDrive ID";
  customDriveInput.style.display = "none";

  const driveLocation = document.createElement("input");
  driveLocation.classList.add("form-input");
  driveLocation.name = "gdrive-location";
  driveLocation.placeholder = "/posters/{folder}";
  selectWrapper.appendChild(driveLocation);

  const removeDrive = document.createElement("span");
  removeDrive.classList.add("close");
  removeDrive.innerHTML = "&times;";
  removeDrive.addEventListener("click", handleRemoveDrive);
  if (driveSelectCounter === 0) {
    removeDrive.style.display = "none";
  }

  selectWrapper.appendChild(selectElement);
  selectWrapper.appendChild(customDriveInput);
  selectWrapper.appendChild(driveLocation);
  selectWrapper.appendChild(removeDrive);

  selectElement.addEventListener("change", (event) => {
    if (event.target.value === "custom") {
      selectElement.style.display = "none";
      customDriveInput.style.display = "block";
      customDriveInput.focus();
    }
  });
  customDriveInput.addEventListener("blur", () => {
    if (customDriveInput.value.trim() === "") {
      selectElement.style.display = "block";
      customDriveInput.style.display = "none";
      selectElement.value = "";
    }
  });

  return selectWrapper;
}

function removeDriveSelect(counter) {
  const selectWrapper = document.querySelector(
    `.drive-select-wrapper[data-counter='${counter}']`,
  );
  if (selectWrapper) {
    selectWrapper.remove();
    const driveSelectDiv = document.querySelector(".drive-select-div");
    const driveSelectWrappers = driveSelectDiv.querySelectorAll(
      ".drive-select-wrapper",
    );

    driveSelectWrappers.forEach((wrapper, index) => {
      wrapper.dataset.counter = index;
      const removeDrive = wrapper.querySelector(".close");
      removeDrive.removeEventListener("click", handleRemoveDrive);
      removeDrive.addEventListener("click", handleRemoveDrive);
      if (driveSelectWrappers.length === 1) {
        removeDrive.style.display = "none";
      } else {
        removeDrive.style.display = "inline";
      }
    });
    driveSelectCounter = driveSelectWrappers.length;
  }
}
function handleRemoveDrive(event) {
  const removeButton = event.target;
  const selectWrapper = removeButton.closest(".drive-select-wrapper");
  const counter = selectWrapper.dataset.counter;
  removeDriveSelect(Number(counter));
}

function createModal() {
  const modal = document.createElement("div");
  modal.id = "drive-sync-modal";
  modal.classList.add("modal");

  const modalContent = document.createElement("div");
  modalContent.classList.add("modal-content");

  const closeButton = document.createElement("span");
  closeButton.classList.add("close");
  closeButton.innerHTML = "&times;";
  closeButton.addEventListener("click", () => {
    modal.style.display = "none";
  });

  function createInputField(id, labelText, placeholder, isTextArea = false) {
    const label = document.createElement("label");
    label.classList.add("form-label");
    label.textContent = labelText;

    let input;
    if (isTextArea) {
      input = document.createElement("textarea");
      input.rows = 2;
      input.style.resize = "vertical";
    } else {
      input = document.createElement("input");
      input.type = "text";
    }

    input.classList.add("form-input");
    input.id = id;
    input.placeholder = placeholder;

    modalContent.appendChild(label);
    modalContent.appendChild(input);
  }
  modalContent.appendChild(closeButton);
  modalContent.appendChild(document.createElement("br"));

  createInputField("rclone-client-id", "Client Id", "rclone client id", true);
  createInputField("rclone-secret", "Rclone Secret", "rclone secret");
  createInputField("rclone-token", "Rclone Token", "rclone token", true);
  createInputField(
    "sa-location",
    "Service Account Location",
    "/config/rclone_sa.json",
  );

  modal.appendChild(modalContent);
  return modal;
}

function updateCounter(name) {
  const wrapperDiv = document.getElementById(`${name}-group-wrapper`);

  const formGroups = wrapperDiv.querySelectorAll(".form-group");
  const instanceInputs = wrapperDiv.querySelectorAll(
    `input[name="${name}_instance\\[\\]"]`,
  );
  counters[name] = formGroups.length;
  instanceInputs.forEach((input, index) => {
    input.placeholder = `${name}_${index + 1}`;
  });
  formGroups.forEach((group, index) => {
    group.id = `${name}-group-${index + 1}`;
  });
}
function createInstanceSpan(instanceLabel, name) {
  const instanceSpan = document.createElement("span");
  instanceSpan.classList.add("span-group");
  const instanceInput = instanceLabel.querySelector("input");

  const testBtn = document.createElement("button");
  testBtn.id = `test-${name}`;
  testBtn.type = "button";
  testBtn.classList.add("btn", "btn-test");
  testBtn.textContent = "Test";
  instanceSpan.appendChild(instanceInput);
  instanceSpan.appendChild(testBtn);

  instanceLabel.appendChild(instanceSpan);
  return instanceLabel;
}

function createInstance(name, counter) {
  let dynamicUrlPlaceholder;
  let dynamicApiPlaceholder;

  if (name === "radarr") {
    dynamicUrlPlaceholder = "http://localhost:7878";
  } else if (name === "sonarr") {
    dynamicUrlPlaceholder = "http://localhost:8989";
  } else {
    dynamicUrlPlaceholder = "http://localhost:32400";
  }
  if ((name === "radarr") | (name === "sonarr")) {
    dynamicApiPlaceholder = "api-key";
  } else {
    dynamicApiPlaceholder = "plex-token";
  }

  const formGroup = document.createElement("div");
  formGroup.id = `${name}-group-${counter}`;
  formGroup.classList.add("form-group");

  const separator = document.createElement("hr");
  separator.classList.add("separator");

  const instanceInput = createInput(`${name}_instance`, `${name}_${counter}`);
  const instanceLabel = createLabel("Instance", instanceInput.name);
  instanceLabel.appendChild(instanceInput);

  const urlInput = createInput(`${name}_url`, dynamicUrlPlaceholder);
  const urlLabel = createLabel("URL", urlInput.name);
  urlLabel.appendChild(urlInput);

  const apiInput = createInput(`${name}_api`, dynamicApiPlaceholder);
  const apiLabel = createLabel("API", apiInput.name);
  apiLabel.appendChild(apiInput);

  const instanceSpan = createInstanceSpan(instanceLabel, name);

  if (counters[name] > 1) {
    formGroup.appendChild(separator);
  }
  formGroup.appendChild(instanceSpan);
  formGroup.appendChild(urlLabel);
  formGroup.appendChild(apiLabel);

  return formGroup;
}

// Add extra Radarr instance

function attachNewInstance(name) {
  counters[name]++;
  const wrapperDiv = document.getElementById(`${name}-group-wrapper`);
  const newInstance = createInstance(name, counters[name]);
  const testButton = newInstance.querySelector(".btn-test");
  attachTestButtonListener(testButton, name);

  wrapperDiv.appendChild(newInstance);
  attachRemoveButton(wrapperDiv, name, newInstance);
  if (counters[name] === 1) {
    hideAllRemoveButtons(name);
  } else {
    const removeButtons = wrapperDiv.querySelectorAll(".btn-remove");
    removeButtons.forEach((button) => {
      button.style.display = "block";
    });
  }
}

function attachRemoveButton(wrapperDiv, name, formGroup) {
  const instanceSpans = wrapperDiv.querySelectorAll(".span-group");
  instanceSpans.forEach((group) => {
    if (!group.querySelector(".btn-remove")) {
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.classList.add("btn", "btn-primary", "btn-remove");
      removeButton.innerHTML = '<i class="fas fa-trash-alt"></i>';
      group.appendChild(removeButton);
      removeButton.addEventListener("click", function () {
        const isFirstInstance = formGroup === wrapperDiv.firstElementChild;
        const nextSibling = formGroup.nextElementSibling;
        if (isFirstInstance && nextSibling) {
          const nextSeparator = nextSibling.querySelector(".separator");
          if (nextSeparator) {
            nextSeparator.remove();
          }
        }
        formGroup.remove();
        counters[name]--;
        updateCounter(name);
        if (counters[name] === 1) {
          hideAllRemoveButtons(name);
        }
      });
    }
  });
}

function createLogLevelGroup(name, inputId) {
  const wrapperDiv = document.createElement("div");
  wrapperDiv.classList.add("log-level-group");

  const scriptName = document.createElement("label");
  scriptName.classList.add("form-name");
  scriptName.textContent = `${name}`;
  const separator = document.createElement("hr");
  separator.classList.add("separator");

  const checkboxDiv = document.createElement("div");
  checkboxDiv.classList.add("form-group-checkbox");

  const infoCheckbox = createCheckboxInput(
    "INFO",
    `${inputId}_info`,
    `${inputId}_log_level`,
    "info",
  );

  const debugCheckbox = createCheckboxInput(
    "DEBUG",
    `${inputId}_debug`,
    `${inputId}_log_level`,
    "debug",
  );

  const infoInput = infoCheckbox.querySelector("input");
  const debugInput = debugCheckbox.querySelector("input");

  infoInput.onclick = () => {
    if (infoInput.checked) {
      debugInput.checked = false;
    } else {
      debugInput.checked = true;
    }
  };
  debugInput.onclick = () => {
    if (debugInput.checked) {
      infoInput.checked = false;
    } else {
      infoInput.checked = true;
    }
  };

  checkboxDiv.appendChild(infoCheckbox);
  checkboxDiv.appendChild(debugCheckbox);

  wrapperDiv.appendChild(scriptName);
  wrapperDiv.appendChild(checkboxDiv);
  wrapperDiv.appendChild(separator);
  return wrapperDiv;
}

function hideAllRemoveButtons(name) {
  const wrapperDiv = document.getElementById(`${name}-group-wrapper`);
  const removeButtons = wrapperDiv.querySelectorAll(".btn-remove");
  removeButtons.forEach((button) => {
    button.style.display = "none";
  });
}

document.getElementById("add-radarr").addEventListener("click", function () {
  attachNewInstance("radarr");
});

// Add Sonarr instance

document.getElementById("add-sonarr").addEventListener("click", function () {
  attachNewInstance("sonarr");
});

// Add Plex instance

document.getElementById("add-plex").addEventListener("click", function () {
  attachNewInstance("plex");
});

function captureDriveSelections() {
  const driveDataMap = new Map();
  const driveSelectWrappers = document.querySelectorAll(
    ".drive-select-wrapper",
  );
  driveSelectWrappers.forEach((wrapper) => {
    const selectElement = wrapper.querySelector("select[name='gdrive-select']");
    const customInput = wrapper.querySelector("input[name='custom-drive-id']");
    const locationInput = wrapper.querySelector(
      "input[name='gdrive-location']",
    );

    let driveId = selectElement.value;
    let driveName =
      selectElement.options[selectElement.selectedIndex]?.text || "";

    if (driveId === "custom") {
      driveId = customInput.value.trim();
      driveName = "Custom";
    }
    const driveLocation = locationInput.value.trim();
    if (driveId) {
      driveDataMap.set(driveId, {
        name: driveName,
        id: driveId,
        location: driveLocation,
      });
    }
  });
  return driveDataMap;
}
function captureRcloneConf() {
  return {
    client_id: document.getElementById("rclone-client-id")?.value.trim() || "",
    rclone_token: document.getElementById("rclone-token")?.value.trim() || "",
    rclone_secret: document.getElementById("rclone-secret")?.value.trim() || "",
    sa_location: document.getElementById("sa-location")?.value.trim() || "",
  };
}

// Save settings to db
function attachSaveSettingsListener(saveButton) {
  saveButton.addEventListener("click", function () {
    const requiredFields = [
      'input[name="target_path"]',
      'input[name="source_dir[]"]',
      'input[name="library_name[]"]',
      'input[name="instance[]"]',
      'input[name="radarr_instance[]"]',
      'input[name="radarr_url[]"]',
      'input[name="radarr_api[]"]',
      'input[name="sonarr_instance[]"]',
      'input[name="sonarr_url[]"]',
      'input[name="sonarr_api[]"]',
      'input[name="plex_instance[]"]',
      'input[name="plex_url[]"]',
      'input[name="plex_api[]"]',
    ];

    const emptyFields = requiredFields.filter((selector) => {
      const inputs = document.querySelectorAll(selector);
      return Array.from(inputs).some((input) => !input.value.trim());
    });
    if (emptyFields.length > 0) {
      alert("Please fill in all required empty fields before saving.");
      return;
    }
    const logLevelPosterRenamer = document.querySelector(
      'input[name="poster-renamer_log_level"]:checked',
    )?.value;
    const logLevelUnmatchedAssets = document.querySelector(
      'input[name="unmatched-assets_log_level"]:checked',
    )?.value;
    const logLevelPlexUploaderr = document.querySelector(
      'input[name="plex-uploaderr_log_level"]:checked',
    )?.value;
    const logLevelBorderReplacerr = document.querySelector(
      'input[name="border-replacerr_log_level"]:checked',
    )?.value;
    const targetPath = document.querySelector(
      'input[name="target_path"]',
    ).value;
    const posterRenamerSchedule = document.querySelector(
      'input[name="poster_renamer_schedule"]',
    ).value;
    const unmatchedAssetsSchedule = document.querySelector(
      'input[name="unmatched_assets_schedule"]',
    ).value;
    const plexUploaderrSchedule = document.querySelector(
      'input[name="plex_uploaderr_schedule"]',
    ).value;
    const borderSetting = document.querySelector(
      'select[name="border_setting"]',
    ).value;
    const customColor = document.querySelector('input[name="hex_code"]').value;
    const sourceDirs = Array.from(
      document.querySelectorAll('input[name="source_dir[]"]'),
    ).map((input) => input.value);
    const libraryNames = Array.from(
      document.querySelectorAll('input[name="library_name[]"]'),
    ).map((input) => input.value);
    const instances = Array.from(
      document.querySelectorAll('input[name="instance[]"]'),
    ).map((input) => input.value);
    const assetFolders = document.getElementById("asset_folders").checked;
    const replaceBorder = document.getElementById("replace_border").checked;
    const unmatchedAssets = document.getElementById("unmatched_assets").checked;
    const runSingleItem = document.getElementById("run_single_item").checked;
    const onlyUnmatched = document.getElementById("only_unmatched").checked;
    const uploadToPlex = document.getElementById("upload_to_plex").checked;
    const reapplyPosters = document.getElementById("reapply_posters").checked;
    const cleanAssets = document.getElementById("clean_assets").checked;
    const matchAlt = document.getElementById("match_alt").checked;
    const disableUnmatchedCollections = document.getElementById(
      "disable_unmatched_collections",
    ).checked;
    document.getElementById("reapply_posters").checked;
    const showAllUnmatched =
      document.getElementById("show_all_unmatched").checked;
    // radarr
    const radarrInstanceNames = Array.from(
      document.querySelectorAll('input[name="radarr_instance[]"]'),
    ).map((input) => input.value);
    const radarrUrls = Array.from(
      document.querySelectorAll('input[name="radarr_url[]"]'),
    ).map((input) => input.value);
    const radarrApiKeys = Array.from(
      document.querySelectorAll('input[name="radarr_api[]"]'),
    ).map((input) => input.value);

    const radarrInstances = radarrInstanceNames.map((name, index) => ({
      instanceName: name,
      url: radarrUrls[index],
      apiKey: radarrApiKeys[index],
    }));

    // sonarr
    const sonarrInstanceNames = Array.from(
      document.querySelectorAll('input[name="sonarr_instance[]"]'),
    ).map((input) => input.value);
    const sonarrUrls = Array.from(
      document.querySelectorAll('input[name="sonarr_url[]"]'),
    ).map((input) => input.value);
    const sonarrApiKeys = Array.from(
      document.querySelectorAll('input[name="sonarr_api[]"]'),
    ).map((input) => input.value);

    const sonarrInstances = sonarrInstanceNames.map((name, index) => ({
      instanceName: name,
      url: sonarrUrls[index],
      apiKey: sonarrApiKeys[index],
    }));

    // plex
    const plexInstanceNames = Array.from(
      document.querySelectorAll('input[name="plex_instance[]"]'),
    ).map((input) => input.value);
    const plexUrls = Array.from(
      document.querySelectorAll('input[name="plex_url[]"]'),
    ).map((input) => input.value);
    const plexApiKeys = Array.from(
      document.querySelectorAll('input[name="plex_api[]"]'),
    ).map((input) => input.value);

    const plexInstances = plexInstanceNames.map((name, index) => ({
      instanceName: name,
      url: plexUrls[index],
      apiKey: plexApiKeys[index],
    }));

    const gdriveData = Array.from(captureDriveSelections().values());
    const rcloneData = captureRcloneConf();
    console.log(rcloneData);

    fetch("/save-settings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        logLevelUnmatchedAssets: logLevelUnmatchedAssets,
        logLevelPosterRenamer: logLevelPosterRenamer,
        logLevelPlexUploaderr: logLevelPlexUploaderr,
        logLevelBorderReplacerr: logLevelBorderReplacerr,
        posterRenamerSchedule: posterRenamerSchedule,
        unmatchedAssetsSchedule: unmatchedAssetsSchedule,
        plexUploaderrSchedule: plexUploaderrSchedule,
        targetPath: targetPath,
        sourceDirs: sourceDirs,
        libraryNames: libraryNames,
        instances: instances,
        assetFolders: assetFolders,
        cleanAssets: cleanAssets,
        unmatchedAssets: unmatchedAssets,
        replaceBorder: replaceBorder,
        runSingleItem: runSingleItem,
        onlyUnmatched: onlyUnmatched,
        uploadToPlex: uploadToPlex,
        matchAlt: matchAlt,
        reapplyPosters: reapplyPosters,
        showAllUnmatched: showAllUnmatched,
        disableUnmatchedCollections: disableUnmatchedCollections,
        radarrInstances: radarrInstances,
        sonarrInstances: sonarrInstances,
        plexInstances: plexInstances,
        borderSetting: borderSetting,
        customColor: customColor,
        gdriveData: gdriveData,
        rcloneData: rcloneData,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          captureInitialState();
          disableSaveButton();
        } else {
          alert("Error saving settings: " + data.message);
        }
      })
      .catch((error) => {
        console.error("Error", error);
        alert("An unexpected error occurred.");
      });
  });
}

function attachTestButtonListener(testButton, instanceType) {
  testButton.addEventListener("click", function (event) {
    const parentGroup = event.target.closest(".form-group");
    const url = parentGroup.querySelector(
      `input[name="${instanceType}_url[]"]`,
    ).value;
    const apiKey = parentGroup.querySelector(
      `input[name="${instanceType}_api[]"]`,
    ).value;

    fetch(`/test-connection`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: url,
        apiKey: apiKey,
        instanceType: instanceType,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          flashButton(testButton, "green");
        } else {
          flashButton(testButton, "red");
        }
      })
      .catch((error) => {
        console.error("Error", error);
        flashButton(testButton, "red");
      });
  });
}

function flashButton(button, color) {
  const originalBackgroundColor = button.style.backgroundColor;

  button.style.backgroundColor = color;

  setTimeout(() => {
    button.style.backgroundColor = originalBackgroundColor;
  }, 2000);
}
