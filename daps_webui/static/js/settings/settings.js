// TODO: add info hover tip for schedules

/**
 * Initialize the settings page and fetch settings from the server
 */
let initialState = [];

let counters = {
  sonarr: 0,
  radarr: 0,
  plex: 0,
};

let placeholders = {
  targetPath: '/kometa/assets',
  sourceDir: '/posters/Drazzilb08',
  libraryName: 'Movies (HD)',
  instance: 'radarr_1',
  cronSchedule: 'cron(0 */3 * * *)',
};

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

document.addEventListener('DOMContentLoaded', function () {
  attachNewInstance('radarr');
  attachNewInstance('sonarr');
  attachNewInstance('plex');
  attachDriveSync();
  attachSaveSettingsListener(document.querySelector('#save-settings'));

  fetch('/get-settings')
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        preFillForm(data.settings);
        captureInitialState();
        attachInputListeners();
      } else {
        console.error('Error fetching settings: ' + data.message);
      }
    })
    .catch((error) => {
      console.error('Error', error);
    });

  const sourceList = document.getElementById('source_dir_container');
  const settingsContainer = document.getElementById('settings-container');
  // const addButtons = document.querySelectorAll('.btn-add');
  // addButtons.forEach((button) => {
  //   button.addEventListener('click', () => {
  //     disableSaveButton();
  //   });
  // });

  // Mark all of the required fields with an asterisk
  markRequiredFields();

  // Initialize drag and drop functionality
  initializeDragAndDrop(sourceList);

  // Add listeners to the add buttons in Poster Renamerr section
  setupRenamerrAddButtons();

  // debounced observer callbacks for input changes
  const observer = new MutationObserver((mutationList) => {
    clearTimeout(observer.timeout);
    observer.timeout = setTimeout(() => {
      // Batch process all mutations
      const addedNodes = mutationList.reduce((nodes, mutation) => {
        if (mutation.type === 'childList') {
          return nodes.concat(Array.from(mutation.addedNodes));
        }
        return nodes;
      }, []);

      // Single pass to handle new inputs
      const newInputs = addedNodes.filter((node) =>
        node.matches?.('input, select, textarea')
      );

      if (newInputs.length > 0) {
        newInputs.forEach(attachInputListener);
        checkChanges();
      }
    }, 250);
  });

  observer.observe(settingsContainer, {
    childList: true,
    subtree: true,
    attributes: false,
    characterData: false,
  });
});

function attachInputListeners() {
  const inputs = document.querySelectorAll('input, select, textarea');
  inputs.forEach(attachInputListener);
}

function attachInputListener(input) {
  input.addEventListener('input', checkChanges);
  input.addEventListener('change', checkChanges);
}

function captureInitialState() {
  const inputs = document.querySelectorAll('input, select, textarea');
  initialState = Array.from(inputs).map((input) => {
    if (input.type === 'checkbox' || input.type === 'radio') {
      return input.checked;
    }
    return input.value;
  });
  // console.log("Initial state captured:", initialState);
}

function checkChanges() {
  // console.time('checkChanges');
  const inputs = Array.from(
    document.querySelectorAll('input, select, textarea')
  );
  const curentStates = inputs.map((input) => {
    if (input.type === 'checkbox' || input.type === 'radio') {
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
  // console.timeEnd('checkChanges');
}

/**
 * Mark each required field with an asterisk
 */
function markRequiredFields() {
  requiredFields.forEach((selector) => {
    const label = document.querySelector(
      `label[for="${selector.slice(12, -2)}"]`
    );
    if (label) {
      label.classList.add('form-label--required');
      const requiredSpan = document.createElement('span');
      requiredSpan.classList.add('required');
      requiredSpan.textContent = '*';

      // get the text node of the label
      const textNode = Array.from(label.childNodes).find(
        (node) => node.nodeType === Node.TEXT_NODE
      );

      // Insert the span after the text
      if (textNode) {
        textNode.after(requiredSpan);
      }
    }
  });
}

/**
 * Show and hide the custom color input based on the border-setting
 */
function toggleCustomColorInput() {
  const borderColorSelect = document.getElementById('border_select');
  const customColorInput = document.getElementById('custom_color');
  const customColorLabel = document.querySelector('label[for="hex_code"]');

  if (borderColorSelect.value === 'custom') {
    customColorLabel.classList.remove('hidden');
    customColorInput.classList.remove('hidden');
  } else {
    customColorLabel.classList.add('hidden');
    customColorInput.classList.add('hidden');
  }

  borderColorSelect.addEventListener('change', (event) => {
    if (event.target.value === 'custom') {
      customColorLabel.classList.remove('hidden');
      customColorInput.classList.remove('hidden');
    } else {
      customColorLabel.classList.add('hidden');
      customColorInput.classList.add('hidden');
    }
  });
}

/**
 * ---------------------------------
 * Drag and Drop Functionality
 * ---------------------------------
 */
function initializeDragAndDrop(container) {
  container.addEventListener('dragstart', handleDragStart);
  container.addEventListener('dragend', handleDragEnd);
  container.addEventListener('dragover', handleDragOver);
}

function handleDragStart(e) {
  if (e.target.classList.contains('source-item')) {
    e.target.classList.add('dragging');
  }
}

function handleDragEnd(e) {
  e.target.classList.remove('dragging');
  // update the buttons to put the plus button on the last child
  // Since dragging is only supported for source_dirs currently,
  // this can be hardcoded
  const sourceList = document.getElementById('source_dir_container');
  const sourceItems = sourceList.querySelectorAll('.source-item');
  sourceItems.forEach((item) => {
    item.querySelector('.btn-add').classList.add('hidden');
    item.querySelector('.btn-remove').classList.remove('hidden');
    attachRemoveButtonListener(item, sourceList, 'source-dir__group');
  });
  const lastItem = sourceItems[sourceItems.length - 1];
  lastItem.querySelector('.btn-add').classList.remove('hidden');
  lastItem.querySelector('.btn-remove').classList.add('hidden');
  renameItemIds();
}

function handleDragOver(e) {
  e.preventDefault();
  const container = e.currentTarget;
  const afterElement = getDragAfterElement(container, e.clientY);
  const draggingItem = document.querySelector('.dragging');
  if (afterElement == null) {
    container.appendChild(draggingItem);
  } else {
    container.insertBefore(draggingItem, afterElement);
  }
}

function getDragAfterElement(container, y) {
  const draggableElements = [
    ...container.querySelectorAll('.source-item:not(.dragging)'),
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
    { offset: Number.NEGATIVE_INFINITY }
  ).element;
}

function renameItemIds() {
  const items = document.querySelectorAll('.source-item');
  items.forEach((item, index) => {
    item.id = `source_dir_${index + 1}`;
  });
}

/**
 * ---------------------------------
 * Create and Attach Instance inputs
 * loaded from settings
 * ---------------------------------
 */
function createInstanceFromSettings(data, settingsVar, htmlVar) {
  for (let i = 1; i < data[settingsVar].length; i++) {
    attachNewInstance(htmlVar);
  }
  const instanceInputs = document.querySelectorAll(
    `input[name="${htmlVar}_instance[]"]`
  );
  const urlInputs = document.querySelectorAll(`input[name="${htmlVar}_url[]"]`);
  const apiInputs = document.querySelectorAll(`input[name="${htmlVar}_api[]"]`);

  instanceInputs.forEach((input, index) => {
    input.value = data[settingsVar][index]?.instanceName || '';
  });
  urlInputs.forEach((input, index) => {
    input.value = data[settingsVar][index]?.url || '';
  });
  apiInputs.forEach((input, index) => {
    input.value = data[settingsVar][index]?.apiKey || '';
  });
}

function createInputFromSettings(data, settingsVar, htmlVar) {
  for (let i = 1; i < data[settingsVar].length; i++) {
    cloneInput(htmlVar, {
      parentNode: `${htmlVar}_container`,
      cloneSourceList: `${htmlVar.replace('_', '-')}__group`,
      placeholder: placeholders[htmlVar],
      value: data[settingsVar][i],
    });
  }
}

function createDriveFromSettings(data) {
  const driveSelectDiv = document.querySelector('.drive-select-div');
  const driveSelectWrappers = driveSelectDiv.querySelectorAll(
    '.drive-select-wrapper'
  );

  data['gdrives'].forEach((gdrive, index) => {
    let driveSelectWrapper;

    if (index === 0 && driveSelectWrappers.length > 0) {
      driveSelectWrapper = driveSelectWrappers[0];
    } else {
      driveSelectWrapper = createDriveSelect(driveSelectCounter);
      driveSelectDiv.appendChild(driveSelectWrapper);
      driveSelectCounter++;
    }

    const selectElement = driveSelectWrapper.querySelector(
      "select[name='gdrive-select']"
    );
    const locationInput = driveSelectWrapper.querySelector(
      "input[name='gdrive-location']"
    );
    const customInput = driveSelectWrapper.querySelector(
      "input[name='custom-drive-id']"
    );
    if (locationInput) {
      locationInput.value = gdrive.location || '';
    }
    if (selectElement) {
      const optionExists = Array.from(selectElement.options).some(
        (option) => option.value === gdrive.id
      );
      if (optionExists) {
        selectElement.value = gdrive.id;
      } else {
        selectElement.value = 'custom';
        customInput.style.display = 'block';
        customInput.value = gdrive.id;
        selectElement.style.display = 'none';
      }
    }
  });

  if (driveSelectCounter >= 1) {
    driveSelectWrappers.forEach((wrapper) => {
      const removeButton = wrapper.querySelector('.close');
      if (removeButton) {
        removeButton.style.display = 'inline';
      }
    });
  }
}

function preFillForm(data) {
  // Set up Renamerr inputs
  document.querySelector('input[name="poster_renamer_schedule"]').value =
    data.posterRenamerSchedule || '';
  document.querySelector('input[name="target_path"]').value =
    data.targetPath || '';
  document.getElementById('asset_folders').checked = data.assetFolders || false;
  document.getElementById('clean_assets').checked = data.cleanAssets || false;
  document.getElementById('match_alt_titles').checked = data.matchAlt || false;
  document.getElementById('replace_border').checked =
    data.replaceBorder || false;
  document.getElementById('unmatched_assets').checked =
    data.unmatchedAssets || false;
  document.getElementById('run_single_item').checked =
    data.runSingleItem || false;
  document.getElementById('only_unmatched').checked =
    data.onlyUnmatched || false;
  document.getElementById('upload_to_plex').checked =
    data.uploadToPlex || false;

  // Drive sync
  document.querySelector('input[name="drive_sync_schedule"]').value =
    data.driveSyncSchedule || '';
  // document.getElementById("drive-sync_info").checked = true;

  // Create additional inputs for source dirs, library names, and instances
  createInputFromSettings(data, 'sourceDirs', 'source_dir');
  createInputFromSettings(data, 'libraryNames', 'library_name');
  createInputFromSettings(data, 'instances', 'instance');

  // Build the saved instances (radarr, sonarr, plex)
  createInstanceFromSettings(data, 'radarrInstances', 'radarr');
  createInstanceFromSettings(data, 'sonarrInstances', 'sonarr');
  createInstanceFromSettings(data, 'plexInstances', 'plex');

  // Drive sync
  document.getElementById('rclone-client-id').value = data.client_id || '';
  document.getElementById('rclone-token').value = data.rclone_token || '';
  document.getElementById('rclone-secret').value = data.rclone_secret || '';
  document.getElementById('sa-location').value = data.sa_location || '';

  createDriveFromSettings(data);

  if (data.borderSetting) {
    const borderColorSelect = document.querySelector(
      'select[name="border_setting"]'
    );
    if (borderColorSelect) {
      borderColorSelect.value = data.borderSetting;
    }
  }
  attachReplaceBorderToggle();
  toggleCustomColorInput();
  document.querySelector('input[name="hex_code"]').value =
    data.customColor || '';

  // Set unmatched assets inputs
  document.querySelector('input[name="unmatched_assets_schedule"]').value =
    data.unmatchedAssetsSchedule || '';
  document.getElementById('show_all_unmatched').checked =
    data.showAllUnmatched || false;
  document.getElementById('disable_unmatched_collections').checked =
    data.disableUnmatchedCollections || false;

  // Set Plex Uploaderr inputs
  document.querySelector('input[name="plex_uploaderr_schedule"]').value =
    data.plexUploaderrSchedule || '';
  document.getElementById('reapply_posters').checked =
    data.reapplyPosters || false;

  // Set log level inputs
  document.getElementById('poster-renamerr-log-level').checked = false;
  document.getElementById('unmatched-assets-log-level').checked = false;
  document.getElementById('plex-uploaderr-log-level').checked = false;
  document.getElementById('border-replacerr-log-level').checked = false;
  document.getElementById('drive-sync-log-level').checked = false;

  if (data.logLevelPosterRenamer === 'debug') {
    document.getElementById('poster-renamerr-log-level').checked = true;
  }
  if (data.logLevelUnmatchedAssets === 'debug') {
    document.getElementById('unmatched-assets-log-level').checked = true;
  }
  if (data.logLevelPlexUploaderr === 'debug') {
    document.getElementById('plex-uploaderr-log-level').checked = true;
  }
  if (data.logLevelBorderReplacerr === 'debug') {
    document.getElementById('border-replacerr-log-level').checked = true;
  }
  if (data.logLevelDriveSync === 'debug') {
    document.getElementById('drive-sync-log-level').checked = true;
  }
}
function attachDriveSync() {
  const wrapperDiv = document.getElementById('drive-sync-wrapper');
  const driveSync = createDriveSync();
  wrapperDiv.appendChild(driveSync);
}

function createLabel(labelName, inputName) {
  const label = document.createElement('label');
  label.classList.add('form-label');
  label.setAttribute('for', `${inputName}`);
  label.textContent = `${labelName}`;
  return label;
}

function createInput(inputType, placeholder) {
  const input = document.createElement('input');
  input.type = 'text';
  input.name = `${inputType}[]`;
  input.placeholder = placeholder;
  input.classList.add('form-input');
  return input;
}

/**
 * Attach event listener to the "replace border" checkbox
 * that shows/hides the border color input/select
 */
function attachReplaceBorderToggle() {
  const borderReplacerCheckbox = document.getElementById('replace_border');
  const borderColorDiv = document.getElementById('border-setting');
  function toggleBorderColorDiv() {
    if (borderReplacerCheckbox.checked) {
      borderColorDiv.style.display = 'block';
    } else {
      borderColorDiv.style.display = 'none';
    }
  }
  borderReplacerCheckbox.addEventListener('change', toggleBorderColorDiv);
  toggleBorderColorDiv();
}

/**
 * Attach event listener to the add buttons in Poster Renamerr section. Each
 * button will clone the input group and append it to the parent node.
 * @param button
 * @param inputType
 * @param placeholder
 */
function attachAddButtonListener(button, inputType, placeholder) {
  button.addEventListener('click', function () {
    cloneInput(inputType, {
      parentNode: `${inputType}_container`,
      cloneSourceList: `${inputType.replace('_', '-')}__group`,
      placeholder,
    });

    // After the input is cloned, focus on the new input
    const inputList = document.querySelectorAll(`input[name="${inputType}[]"]`);
    inputList[inputList.length - 1].focus();
  });
}

/**
 * Add listeners to the add buttons in Poster Renamerr section
 */
function setupRenamerrAddButtons() {
  attachAddButtonListener(
    document.querySelector('#source_dir_container .btn-add'),
    'source_dir',
    placeholders['sourceDir']
  );
  attachAddButtonListener(
    document.querySelector('#library_name_container .btn-add'),
    'library_name',
    placeholders['libraryName']
  );
  attachAddButtonListener(
    document.querySelector('#instance_container .btn-add'),
    'instance',
    placeholders['instance']
  );
}

/**
 * --------------------------------
 * Drive Sync
 * --------------------------------
 */
let driveSelectCounter = 0;

let availableDrives = {
  drazzilb: '1VeeQ_frBFpp6AZLimaJSSr0Qsrl6Tb7z',
  zarox: '1wOhY88zc0wdQU-QQmhm4FzHL9QiCQnpu',
  solen: '1YEuS1pulJAfhKm4L8U9z5-EMtGl-d2s7',
  bz: '1Xg9Huh7THDbmjeanW0KyRbEm6mGn_jm8',
  iamspartacus: '1aRngLdC9yO93gvSrTI2LQ_I9BSoGD-7o',
  lioncitygaming: '1alseEnUBjH6CjXh77b5L4R-ZDGdtOMFr',
  majorgiant: '1ZfvUgN0qz4lJYkC_iMRjhH-fZ0rDN_Yu',
  sahara: '1KnwxzwBUQzQyKF1e24q_wlFqcER9xYHM',
  stupifier: '1bBbK_3JeXCy3ElqTwkFHaNoNxYgqtLug',
  quafley: '1G77TLQvgs_R7HdMWkMcwHL6vd_96cMp7',
  dsaq: '1wrSru-46iIN1iqCl2Cjhj5ofdazPgbsz',
  overbook874: '1LIVG1RbTEd7tTJMbzZr7Zak05XznLFia',
  mareau: '1hEY9qEdXVDzIbnQ4z9Vpo0SVXXuZBZR-',
  tokenminal: '1KJlsnMz-z2RAfNxKZp7sYP_U0SD1V6lS',
  kalyanrajnish: '1Kb1kFZzzKKlq5N_ob8AFxJvStvm9PdiL',
  minimyself: '1ZhcV8Ybja4sJRrVze-twOmb8fEZfZ2Ci',
  theotherguy_1: '1TYVIGKpSwhipLyVQQn_OJHTobM6KaokB',
  theotherguy_2: '15faKB1cDQAhjTQCvj8MvGUQb0nBORWGC',
  reitenth: '1cqDinU27cnHf5sL5rSlfO7o_T6LSxG77',
  wenisinmood: '1Wz0S18sKOeyBURkJ1uT3RtkEmSsK1-PG',
  jpalenz77: '1qBC7p9K4zur5dOCf3F6VTyUROVvHQoSb',
  chrisdc: '1oBzEOXXrTHGq6sUY_4RMtzMTt4VHyeJp',
  majorgiant_2: '15sNlcFZmeDox2OQJyGjVxRwtigtd82Ru',
  iamspartacus_2: '1-WhCVwRLfV6hxyKF7W5IuzIHIYicCdAv',
  solen_2: '1zWY-ORtJkOLcQChV--oHquxW3JCow1zm',
};

function createDriveSync() {
  const wrapperDiv = document.createElement('div');

  const cronScheduleInput = document.createElement('input');
  cronScheduleInput.name = 'drive_sync_schedule';
  cronScheduleInput.type = 'text';
  cronScheduleInput.classList.add('form-input');
  cronScheduleInput.placeholder = placeholders['cronSchedule'];
  const cronScheduleLabel = createTitle('Schedule');

  const driveSelectDiv = document.createElement('div');
  driveSelectDiv.classList.add('drive-select-div');

  const driveLabel = document.createElement('span');
  driveLabel.textContent = 'G-Drives';
  driveLabel.classList.add('form-label');

  const firstDriveSelect = createDriveSelect(driveSelectCounter);
  driveSelectCounter++;
  driveSelectDiv.appendChild(firstDriveSelect);

  const buttonDiv = document.createElement('div');
  buttonDiv.classList.add('button-div');

  const configureButton = document.createElement('button');
  configureButton.id = 'configure-drive-sync';
  configureButton.type = 'button';
  configureButton.classList.add('btn', 'btn-primary');
  configureButton.textContent = 'Configure';
  buttonDiv.appendChild(configureButton);

  const addDriveButton = document.createElement('button');
  addDriveButton.id = 'add-drive-button';
  addDriveButton.type = 'button';
  addDriveButton.classList.add('btn', 'btn-primary');
  addDriveButton.textContent = '+ Add GDrive';
  buttonDiv.appendChild(addDriveButton);

  wrapperDiv.appendChild(cronScheduleLabel);
  wrapperDiv.appendChild(cronScheduleInput);
  wrapperDiv.appendChild(driveLabel);
  wrapperDiv.appendChild(driveSelectDiv);
  wrapperDiv.appendChild(buttonDiv);

  const modal = createModal();
  wrapperDiv.appendChild(modal);

  configureButton.addEventListener('click', () => {
    modal.style.display = 'block';
  });

  addDriveButton.addEventListener('click', () => {
    const dynamicSelect = createDriveSelect(driveSelectCounter);
    driveSelectDiv.appendChild(dynamicSelect);
    if (driveSelectCounter >= 1) {
      const firstDriveSelect = driveSelectDiv.querySelector(
        ".drive-select-wrapper[data-counter='0']"
      );
      if (firstDriveSelect) {
        const firstRemoveButton = firstDriveSelect.querySelector('.close');
        firstRemoveButton.style.display = 'inline';
      }
    }
    driveSelectCounter++;
  });

  return wrapperDiv;
}

function createDriveSelect(counter) {
  const selectWrapper = document.createElement('div');
  selectWrapper.classList.add('drive-select-wrapper');
  selectWrapper.dataset.counter = counter;

  const selectElement = document.createElement('select');
  selectElement.classList.add('form-select');
  selectElement.name = 'gdrive-select';

  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'Select a drive...';
  defaultOption.selected = true;
  defaultOption.disabled = true;
  selectElement.appendChild(defaultOption);

  Object.entries(availableDrives).forEach(([name, id]) => {
    const optionElement = document.createElement('option');
    optionElement.value = id;
    optionElement.textContent = name;
    selectElement.appendChild(optionElement);
  });

  const customDrive = document.createElement('option');
  customDrive.value = 'custom';
  customDrive.textContent = 'Custom Drive ID...';
  selectElement.appendChild(customDrive);

  const customDriveInput = document.createElement('input');
  customDriveInput.classList.add('form-input');
  customDriveInput.name = 'custom-drive-id';
  customDriveInput.placeholder = 'Enter GDrive ID';
  customDriveInput.style.display = 'none';

  const driveLocation = document.createElement('input');
  driveLocation.classList.add('form-input');
  driveLocation.name = 'gdrive-location';
  driveLocation.placeholder = '/posters/{folder}';
  selectWrapper.appendChild(driveLocation);

  const removeDrive = document.createElement('span');
  removeDrive.classList.add('close');
  removeDrive.innerHTML = '&times;';
  removeDrive.addEventListener('click', handleRemoveDrive);
  if (driveSelectCounter === 0) {
    removeDrive.style.display = 'none';
  }

  selectWrapper.appendChild(selectElement);
  selectWrapper.appendChild(customDriveInput);
  selectWrapper.appendChild(driveLocation);
  selectWrapper.appendChild(removeDrive);

  selectElement.addEventListener('change', (event) => {
    if (event.target.value === 'custom') {
      selectElement.style.display = 'none';
      customDriveInput.style.display = 'block';
      customDriveInput.focus();
    }
  });
  customDriveInput.addEventListener('blur', () => {
    if (customDriveInput.value.trim() === '') {
      selectElement.style.display = 'block';
      customDriveInput.style.display = 'none';
      selectElement.value = '';
    }
  });

  return selectWrapper;
}

function removeDriveSelect(counter) {
  const selectWrapper = document.querySelector(
    `.drive-select-wrapper[data-counter='${counter}']`
  );
  if (selectWrapper) {
    selectWrapper.remove();
    const driveSelectDiv = document.querySelector('.drive-select-div');
    const driveSelectWrappers = driveSelectDiv.querySelectorAll(
      '.drive-select-wrapper'
    );

    driveSelectWrappers.forEach((wrapper, index) => {
      wrapper.dataset.counter = index;
      const removeDrive = wrapper.querySelector('.close');
      removeDrive.removeEventListener('click', handleRemoveDrive);
      removeDrive.addEventListener('click', handleRemoveDrive);
      if (driveSelectWrappers.length === 1) {
        removeDrive.style.display = 'none';
      } else {
        removeDrive.style.display = 'inline';
      }
    });
    driveSelectCounter = driveSelectWrappers.length;
  }
}
function handleRemoveDrive(event) {
  const removeButton = event.target;
  const selectWrapper = removeButton.closest('.drive-select-wrapper');
  const counter = selectWrapper.dataset.counter;
  removeDriveSelect(Number(counter));
}

function createModal() {
  const modal = document.createElement('div');
  modal.id = 'drive-sync-modal';
  modal.classList.add('modal');

  const modalContent = document.createElement('div');
  modalContent.classList.add('modal-content');

  const closeButton = document.createElement('span');
  closeButton.classList.add('close');
  closeButton.innerHTML = '&times;';
  closeButton.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  function createInputField(id, labelText, placeholder, isTextArea = false) {
    const label = document.createElement('span');
    label.classList.add('form-label');
    label.textContent = labelText;

    let input;
    if (isTextArea) {
      input = document.createElement('textarea');
      input.rows = 2;
      input.style.resize = 'vertical';
    } else {
      input = document.createElement('input');
      input.type = 'text';
    }

    input.classList.add('form-input');
    input.id = id;
    input.placeholder = placeholder;

    modalContent.appendChild(label);
    modalContent.appendChild(input);
  }
  modalContent.appendChild(closeButton);
  modalContent.appendChild(document.createElement('br'));

  createInputField('rclone-client-id', 'Client Id', 'rclone client id', true);
  createInputField('rclone-secret', 'Rclone Secret', 'rclone secret');
  createInputField('rclone-token', 'Rclone Token', 'rclone token', true);
  createInputField(
    'sa-location',
    'Service Account Location',
    '/config/rclone_sa.json'
  );

  modal.appendChild(modalContent);
  return modal;
}

/**
 * Update the counter for each instance group (radarr, sonarr, plex)
 */
function updateCounter(name) {
  const wrapperDiv = document.getElementById(`${name}-group-wrapper`);

  const formGroups = wrapperDiv.querySelectorAll('.form-group');
  const instanceInputs = wrapperDiv.querySelectorAll(
    `input[name="${name}_instance\\[\\]"]`
  );
  counters[name] = formGroups.length;
  instanceInputs.forEach((input, index) => {
    input.placeholder = `${name}_${index + 1}`;
  });
  formGroups.forEach((group, index) => {
    group.id = `${name}-group-${index + 1}`;
  });
}

/**
 * ---------------------------------
 * Build, instantiate, and set up
 * event listeners for instances
 * ---------------------------------
 */
function createInstanceSpan(instanceLabel, name) {
  const instanceSpan = document.createElement('span');
  instanceSpan.classList.add('span-group');
  const instanceInput = instanceLabel.querySelector('input');

  const testBtn = document.createElement('button');
  testBtn.id = `test-${name}`;
  testBtn.type = 'button';
  testBtn.classList.add('btn', 'btn-test', 'mt-1.5');
  testBtn.textContent = 'Test';
  instanceSpan.appendChild(instanceInput);
  instanceSpan.appendChild(testBtn);

  instanceLabel.appendChild(instanceSpan);
  return instanceLabel;
}

function createInstance(name, counter) {
  let dynamicUrlPlaceholder;
  let dynamicApiPlaceholder;

  if (name === 'radarr') {
    dynamicUrlPlaceholder = 'http://localhost:7878';
  } else if (name === 'sonarr') {
    dynamicUrlPlaceholder = 'http://localhost:8989';
  } else {
    dynamicUrlPlaceholder = 'http://localhost:32400';
  }
  if ((name === 'radarr') | (name === 'sonarr')) {
    dynamicApiPlaceholder = 'api-key';
  } else {
    dynamicApiPlaceholder = 'plex-token';
  }

  const formGroup = document.createElement('div');
  formGroup.id = `${name}-group-${counter}`;
  formGroup.classList.add('form-group');

  const separator = document.createElement('hr');
  separator.classList.add('separator');

  const instanceInput = createInput(`${name}_instance`, `${name}_${counter}`);
  const instanceLabel = createLabel('Instance', instanceInput.name);
  instanceLabel.appendChild(instanceInput);

  const urlInput = createInput(`${name}_url`, dynamicUrlPlaceholder);
  const urlLabel = createLabel('URL', urlInput.name);
  urlLabel.appendChild(urlInput);

  const apiInput = createInput(`${name}_api`, dynamicApiPlaceholder);
  const apiLabel = createLabel('API', apiInput.name);
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

function attachNewInstance(name) {
  counters[name]++;
  const wrapperDiv = document.getElementById(`${name}-group-wrapper`);
  const newInstance = createInstance(name, counters[name]);
  const testButton = newInstance.querySelector('.btn-test');
  attachTestButtonListener(testButton, name);

  wrapperDiv.appendChild(newInstance);
  attachRemoveButton(wrapperDiv, name, newInstance);
  if (counters[name] === 1) {
    hideAllRemoveButtons(name);
  } else {
    const removeButtons = wrapperDiv.querySelectorAll('.btn-remove');
    removeButtons.forEach((button) => {
      button.style.display = 'block';
    });
  }
}

function attachRemoveButton(wrapperDiv, name, formGroup) {
  const instanceSpans = wrapperDiv.querySelectorAll('.span-group');
  instanceSpans.forEach((group) => {
    if (!group.querySelector('.btn-remove')) {
      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.classList.add('btn', 'btn-primary', 'btn-remove', 'mt-1.5');
      removeButton.innerHTML = '<i class="fas fa-trash-alt"></i>';
      group.appendChild(removeButton);
      removeButton.addEventListener('click', function () {
        const isFirstInstance = formGroup === wrapperDiv.firstElementChild;
        const nextSibling = formGroup.nextElementSibling;
        if (isFirstInstance && nextSibling) {
          const nextSeparator = nextSibling.querySelector('.separator');
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

function hideAllRemoveButtons(name) {
  const wrapperDiv = document.getElementById(`${name}-group-wrapper`);
  const removeButtons = wrapperDiv.querySelectorAll('.btn-remove');
  removeButtons.forEach((button) => {
    button.style.display = 'none';
  });
}

// Add Radarr instance
document.getElementById('add-radarr').addEventListener('click', function () {
  attachNewInstance('radarr');
});

// Add Sonarr instance
document.getElementById('add-sonarr').addEventListener('click', function () {
  attachNewInstance('sonarr');
});

// Add Plex instance
document.getElementById('add-plex').addEventListener('click', function () {
  attachNewInstance('plex');
});

/**
 * Attach event listener to the "test" button for each instance
 */
function attachTestButtonListener(testButton, instanceType) {
  testButton.addEventListener('click', function (event) {
    const parentGroup = event.target.closest('.form-group');
    const url = parentGroup.querySelector(
      `input[name="${instanceType}_url[]"]`
    ).value;
    const apiKey = parentGroup.querySelector(
      `input[name="${instanceType}_api[]"]`
    ).value;

    fetch(`/test-connection`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
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
          flashButton(testButton, 'var(--success-dark)');
        } else {
          flashButton(testButton, 'var(--primary-dark)');
        }
      })
      .catch((error) => {
        console.error('Error', error);
        flashButton(testButton, 'var(--primary-dark)');
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

/**
 * ---------------------------------
 * Save Settings to the db
 * ---------------------------------
 */
function enableSaveButton() {
  const saveButton = document.getElementById('save-settings');
  saveButton.disabled = false;
  saveButton.classList.add('enabled');
  const saveText = saveButton.querySelector('span');
  if (saveText) {
    saveText.textContent = 'Save Changes';
  }
}

function disableSaveButton() {
  const saveButton = document.getElementById('save-settings');
  saveButton.disabled = true;
  saveButton.classList.remove('enabled');
  const saveText = saveButton.querySelector('span');
  if (saveText) {
    saveText.textContent = 'No Changes';
  }
}

function captureDriveSelections() {
  const driveDataMap = new Map();
  const driveSelectWrappers = document.querySelectorAll(
    '.drive-select-wrapper'
  );
  driveSelectWrappers.forEach((wrapper) => {
    const selectElement = wrapper.querySelector("select[name='gdrive-select']");
    const customInput = wrapper.querySelector("input[name='custom-drive-id']");
    const locationInput = wrapper.querySelector(
      "input[name='gdrive-location']"
    );

    let driveId = selectElement.value;
    let driveName =
      selectElement.options[selectElement.selectedIndex]?.text || '';

    if (driveId === 'custom') {
      driveId = customInput.value.trim();
      driveName = 'Custom';
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
    client_id: document.getElementById('rclone-client-id')?.value.trim() || '',
    rclone_token: document.getElementById('rclone-token')?.value.trim() || '',
    rclone_secret: document.getElementById('rclone-secret')?.value.trim() || '',
    sa_location: document.getElementById('sa-location')?.value.trim() || '',
  };
}

function attachSaveSettingsListener(saveButton) {
  saveButton.addEventListener('click', function () {
    const emptyFields = requiredFields.filter((selector) => {
      const inputs = document.querySelectorAll(selector);
      return Array.from(inputs).some((input) => !input.value.trim());
    });
    if (emptyFields.length > 0) {
      alert('Please fill in all required empty fields before saving.');
      return;
    }
    const logLevelPosterRenamer = document.querySelector(
      'input[name="poster-renamerr_log_level"]:checked'
    )?.value;
    const logLevelUnmatchedAssets = document.querySelector(
      'input[name="unmatched-assets_log_level"]:checked'
    )?.value;
    const logLevelPlexUploaderr = document.querySelector(
      'input[name="plex-uploaderr_log_level"]:checked'
    )?.value;
    const logLevelBorderReplacerr = document.querySelector(
      'input[name="border-replacerr_log_level"]:checked'
    )?.value;
    const logLevelDriveSync = document.querySelector(
      'input[name="drive-sync_log_level"]:checked'
    )?.value;
    const targetPath = document.querySelector(
      'input[name="target_path"]'
    ).value;
    const posterRenamerSchedule = document.querySelector(
      'input[name="poster_renamer_schedule"]'
    ).value;
    const unmatchedAssetsSchedule = document.querySelector(
      'input[name="unmatched_assets_schedule"]'
    ).value;
    const plexUploaderrSchedule = document.querySelector(
      'input[name="plex_uploaderr_schedule"]'
    ).value;
    const driveSyncSchedule = document.querySelector(
      'input[name="drive_sync_schedule"]'
    ).value;
    const borderSetting = document.querySelector(
      'select[name="border_setting"]'
    ).value;
    const customColor = document.querySelector('input[name="hex_code"]').value;
    const sourceDirs = Array.from(
      document.querySelectorAll('input[name="source_dir[]"]')
    ).map((input) => input.value);
    const libraryNames = Array.from(
      document.querySelectorAll('input[name="library_name[]"]')
    ).map((input) => input.value);
    const instances = Array.from(
      document.querySelectorAll('input[name="instance[]"]')
    ).map((input) => input.value);
    const assetFolders = document.getElementById('asset_folders').checked;
    const replaceBorder = document.getElementById('replace_border').checked;
    const unmatchedAssets = document.getElementById('unmatched_assets').checked;
    const runSingleItem = document.getElementById('run_single_item').checked;
    const onlyUnmatched = document.getElementById('only_unmatched').checked;
    const uploadToPlex = document.getElementById('upload_to_plex').checked;
    const reapplyPosters = document.getElementById('reapply_posters').checked;
    const cleanAssets = document.getElementById('clean_assets').checked;
    const matchAlt = document.getElementById('match_alt_titles').checked;
    const disableUnmatchedCollections = document.getElementById(
      'disable_unmatched_collections'
    ).checked;
    document.getElementById('reapply_posters').checked;
    const showAllUnmatched =
      document.getElementById('show_all_unmatched').checked;

    // radarr
    const radarrInstanceNames = Array.from(
      document.querySelectorAll('input[name="radarr_instance[]"]')
    ).map((input) => input.value);
    const radarrUrls = Array.from(
      document.querySelectorAll('input[name="radarr_url[]"]')
    ).map((input) => input.value);
    const radarrApiKeys = Array.from(
      document.querySelectorAll('input[name="radarr_api[]"]')
    ).map((input) => input.value);

    const radarrInstances = radarrInstanceNames.map((name, index) => ({
      instanceName: name,
      url: radarrUrls[index],
      apiKey: radarrApiKeys[index],
    }));

    // sonarr
    const sonarrInstanceNames = Array.from(
      document.querySelectorAll('input[name="sonarr_instance[]"]')
    ).map((input) => input.value);
    const sonarrUrls = Array.from(
      document.querySelectorAll('input[name="sonarr_url[]"]')
    ).map((input) => input.value);
    const sonarrApiKeys = Array.from(
      document.querySelectorAll('input[name="sonarr_api[]"]')
    ).map((input) => input.value);

    const sonarrInstances = sonarrInstanceNames.map((name, index) => ({
      instanceName: name,
      url: sonarrUrls[index],
      apiKey: sonarrApiKeys[index],
    }));

    // plex
    const plexInstanceNames = Array.from(
      document.querySelectorAll('input[name="plex_instance[]"]')
    ).map((input) => input.value);
    const plexUrls = Array.from(
      document.querySelectorAll('input[name="plex_url[]"]')
    ).map((input) => input.value);
    const plexApiKeys = Array.from(
      document.querySelectorAll('input[name="plex_api[]"]')
    ).map((input) => input.value);

    const plexInstances = plexInstanceNames.map((name, index) => ({
      instanceName: name,
      url: plexUrls[index],
      apiKey: plexApiKeys[index],
    }));

    const gdriveData = Array.from(captureDriveSelections().values());
    const rcloneData = captureRcloneConf();
    // console.log(rcloneData);

    fetch('/save-settings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        logLevelUnmatchedAssets: logLevelUnmatchedAssets,
        logLevelPosterRenamer: logLevelPosterRenamer,
        logLevelPlexUploaderr: logLevelPlexUploaderr,
        logLevelBorderReplacerr: logLevelBorderReplacerr,
        logLevelDriveSync: logLevelDriveSync,
        posterRenamerSchedule: posterRenamerSchedule,
        unmatchedAssetsSchedule: unmatchedAssetsSchedule,
        plexUploaderrSchedule: plexUploaderrSchedule,
        driveSyncSchedule: driveSyncSchedule,
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
          alert('Error saving settings: ' + data.message);
        }
      })
      .catch((error) => {
        console.error('Error', error);
        alert('An unexpected error occurred.');
      });
  });
}

/**
 * ---------------------------------
 * Clone Renamerr Inputs and attach
 * event listeners
 * ---------------------------------
 */

/**
 * Clone an input group and handle event listeners for buttons
 * @param input String The Input type
 * @param props Object The properties of the input
 *
 * props = {
 *   parentNode: string;
 *   cloneSourceList: string;
 *   placeholder: string;
 *   value?: string;
 * }
 */
function cloneInput(input, props) {
  if (!validateProps(props)) {
    throw new Error('Missing required props');
  }
  handleCloning(input, props);
}

/**
 * Validate all of the props are present for cloning inputs
 * @param props Object The properties of the input
 */
function validateProps(props) {
  const required = ['parentNode', 'cloneSourceList', 'placeholder'];
  return required.every((prop) => props.hasOwnProperty(prop));
}

/**
 * Clone the elements and set up event listeners
 * @param input String The Input type
 * @param props Object The properties of the input
 */
function handleCloning(input, props) {
  const parentNode = document.querySelector(`#${props.parentNode}`);
  const cloneSourceList = document.querySelectorAll(
    `.${props.cloneSourceList}`
  );
  const cloneSource = cloneSourceList[cloneSourceList.length - 1];

  const clone = cloneSource.cloneNode(true);
  clone.querySelector('.form-input').value = props.value || '';
  clone.querySelector('.form-input').placeholder = props.placeholder;
  attachInputListener(clone.querySelector('.form-input'));

  const addButton = cloneSource.querySelector('.btn-add');
  clone.querySelector('.btn-add').classList.remove('hidden');
  addButton.classList.add('hidden');

  cloneSource.querySelector('.btn-remove').classList.remove('hidden');
  attachRemoveButtonListener(cloneSource, parentNode, props.cloneSourceList);
  parentNode.appendChild(clone);
  attachAddButtonListener(
    clone.querySelector('.btn-add'),
    input,
    props.placeholder
  );
}

/**
 * Attach an event listener to the remove button
 * @param element Node The element to attach the event listener to
 * @param parentNode Node The parent node of the element
 * @param props Object The properties of the input
 */
function attachRemoveButtonListener(element, parentNode, sourceList) {
  element.querySelector('.btn-remove').addEventListener('click', function () {
    element.remove();
    const remainingInputs = parentNode.querySelectorAll(`.${sourceList}`);
    if (remainingInputs.length === 1) {
      remainingInputs[0].querySelector('.btn-remove').classList.add('hidden');
      remainingInputs[0].querySelector('.btn-add').classList.remove('hidden');
    }
  });
}
