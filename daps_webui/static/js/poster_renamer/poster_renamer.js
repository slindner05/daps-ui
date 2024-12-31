document.addEventListener("DOMContentLoaded", function () {
  createPosterRenamerBox();
  function handleClick() {
    const firstTabLink = document.querySelector(".tab-links");
    const firstFileLink = document.querySelector(".file-link");
    if (firstTabLink && firstFileLink) {
      setTimeout(() => {
        firstTabLink.click();
      }, 100);
      firstFileLink.click();
      observer.disconnect();
    }
  }
  const observer = new MutationObserver(handleClick);
  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
});

fetch("/poster-renamer/get-file-paths")
  .then((response) => response.json())
  .then((data) => {
    if (data.success) {
      const sortedFiles = data.sorted_files;
      console.log(sortedFiles);

      const isSortedFilesEmpty =
        sortedFiles.movies.length === 0 &&
        Object.keys(sortedFiles.shows).length === 0 &&
        sortedFiles.collections.length === 0;

      const unmatchedContainer = document.getElementById("unmatched-container");
      if (isSortedFilesEmpty) {
        if (unmatchedContainer) {
          unmatchedContainer.style.display = "none";
        }
        return;
      }

      const allFiles = [
        ...sortedFiles.movies,
        ...Object.values(sortedFiles.shows),
        ...sortedFiles.collections,
      ];
      populateTab("all", allFiles);
      populateTab("movies", sortedFiles.movies);
      populateTab("series", sortedFiles.shows);
      populateTab("collections", sortedFiles.collections);
    } else {
      console.error("Error fetching images: " + data.message);
    }
  })
  .catch((error) => {
    console.error("Error:", error);
  });

fetch("/poster-renamer/unmatched")
  .then((response) => response.json())
  .then((data) => {
    if (data.success) {
      const unmatchedMedia = data.unmatched_media;
      const unmatchedCounts = data.unmatched_counts;
      const disableCollections = data.disable_collections;
      populateUnmatchedAssetsTable(
        unmatchedMedia,
        unmatchedCounts,
        disableCollections,
      );
      // console.log(unmatchedMedia);
      // console.log(unmatchedCounts);
    } else {
      console.error("Error fetching unmatched media: " + data.message);
    }
  })
  .catch((error) => {
    console.error("Error", error);
  });

function createUnmatchedTable(id) {
  const wrapperDiv = document.createElement("div");
  wrapperDiv.classList.add("unmatched-wrapper", "content-box");
  wrapperDiv.id = id;

  const innerDiv = document.createElement("div");
  innerDiv.classList.add("unmatched-inner");

  const table = document.createElement("table");
  table.classList.add("unmatched-table");

  const tableHead = document.createElement("thead");

  const headings = document.createElement("tr");

  const title = document.createElement("th");
  if (id === "unmatched-movies") {
    title.textContent = "Unmatched Movies";
  } else if (id === "unmatched-series") {
    title.textContent = "Unmatched Series";
  } else {
    title.textContent = "Unmatched Collections";
  }
  headings.appendChild(title);

  if (id === "unmatched-series") {
    const missingAssets = document.createElement("th");
    missingAssets.textContent = "Missing";
    headings.appendChild(missingAssets);
  }

  const tableBody = document.createElement("tbody");
  tableBody.classList.add("table-body-wrapper");

  tableHead.appendChild(headings);
  table.appendChild(tableHead);
  table.appendChild(tableBody);
  innerDiv.appendChild(table);
  wrapperDiv.appendChild(innerDiv);
  return wrapperDiv;
}

function createUnmatchedStats() {
  const wrapperDiv = document.createElement("div");
  wrapperDiv.classList.add("unmatched-wrapper", "content-box");
  wrapperDiv.id = "unmatched-all";

  const table = document.createElement("table");
  table.classList.add("unmatched-table");

  const tableHead = document.createElement("thead");

  const headings = document.createElement("tr");

  const type = document.createElement("th");
  type.textContent = "Type";
  headings.appendChild(type);

  const total = document.createElement("th");
  total.textContent = "Total";
  headings.appendChild(total);

  const unmatched = document.createElement("th");
  unmatched.textContent = "Unmatched";
  headings.appendChild(unmatched);

  const percentComplete = document.createElement("th");
  percentComplete.textContent = "Percent Complete";
  headings.appendChild(percentComplete);

  const tableBody = document.createElement("tbody");

  tableHead.appendChild(headings);
  table.appendChild(tableHead);
  table.appendChild(tableBody);
  wrapperDiv.appendChild(table);
  return wrapperDiv;
}

function createAllUnmatchedTables() {
  const unmatchedContainer = document.getElementById("unmatched-container");

  const moviesTable = createUnmatchedTable("unmatched-movies");
  const collectionsTable = createUnmatchedTable("unmatched-collections");
  const seriesTable = createUnmatchedTable("unmatched-series");
  const statsTable = createUnmatchedStats();
  unmatchedContainer.appendChild(moviesTable);
  unmatchedContainer.appendChild(collectionsTable);
  unmatchedContainer.appendChild(seriesTable);
  unmatchedContainer.appendChild(statsTable);
  return unmatchedContainer;
}

function addTableRow(title, missing = null, seasons = []) {
  const row = document.createElement("tr");

  const titleCell = document.createElement("td");
  titleCell.textContent = title;
  row.appendChild(titleCell);

  if (missing !== null || seasons.length > 0) {
    const missingCell = document.createElement("td");
    const contentDiv = document.createElement("div");

    if (missing !== null) {
      const posterStatus = document.createElement("div");
      posterStatus.textContent = `- ${missing}`;
      posterStatus.classList.add("poster-status");
      contentDiv.appendChild(posterStatus);
    }
    if (seasons.length > 0) {
      seasons.forEach((season) => {
        const seasonItem = document.createElement("div");
        seasonItem.classList.add("season-item");
        seasonItem.textContent = `- ${season}`;
        contentDiv.appendChild(seasonItem);
      });
    }
    missingCell.appendChild(contentDiv);
    row.appendChild(missingCell);
  }
  return row;
}

function addStatsTableRow(type, total, unmatchedTotal, percentComplete) {
  const row = document.createElement("tr");

  const typeCell = document.createElement("td");
  typeCell.textContent = type;
  row.appendChild(typeCell);

  const totalCell = document.createElement("td");
  totalCell.textContent = total;
  row.appendChild(totalCell);

  const unmatchedTotalCell = document.createElement("td");
  unmatchedTotalCell.textContent = unmatchedTotal;
  row.appendChild(unmatchedTotalCell);

  const percentCompleteCell = document.createElement("td");
  percentCompleteCell.textContent = percentComplete;
  row.appendChild(percentCompleteCell);
  return row;
}

function populateUnmatchedAssetsTable(
  unmatchedAssets,
  unmatchedStats,
  disableCollections,
) {
  const movieTableBody = document
    .getElementById("unmatched-movies")
    .querySelector("tbody");
  movieTableBody.innerHTML = "";

  const collectionTableBody = document
    .getElementById("unmatched-collections")
    .querySelector("tbody");
  collectionTableBody.innerHTML = "";

  const seriesTableBody = document
    .getElementById("unmatched-series")
    .querySelector("tbody");
  seriesTableBody.innerHTML = "";

  const statsTableBody = document
    .getElementById("unmatched-all")
    .querySelector("tbody");
  statsTableBody.innerHTML = "";

  const statsMoviesRow = addStatsTableRow(
    "Movies",
    unmatchedStats.total_movies,
    unmatchedStats.unmatched_movies,
    unmatchedStats.percent_complete_movies,
  );
  const statsSeriesRow = addStatsTableRow(
    "Series",
    unmatchedStats.total_series,
    unmatchedStats.unmatched_series,
    unmatchedStats.percent_complete_series,
  );
  const statsSeasonsRow = addStatsTableRow(
    "Seasons",
    unmatchedStats.total_seasons,
    unmatchedStats.unmatched_seasons,
    unmatchedStats.percent_complete_seasons,
  );
  const statsCollectionsRow = addStatsTableRow(
    "Collections",
    unmatchedStats.total_collections,
    unmatchedStats.unmatched_collections,
    unmatchedStats.percent_complete_collections,
  );

  let grandTotal = unmatchedStats.grand_total;
  let unmatchedGrandTotal = unmatchedStats.unmatched_grand_total;
  let percentCompleteGrandTotal = unmatchedStats.percent_complete_grand_total;
  if (disableCollections) {
    grandTotal -= unmatchedStats.total_collections;
    unmatchedGrandTotal -= unmatchedStats.unmatched_collections;
    percentCompleteGrandTotal =
      grandTotal > 0
        ? `${(((grandTotal - unmatchedGrandTotal) / grandTotal) * 100).toFixed(2)}%`
        : "100%";
  }

  const statsGrandTotalRow = addStatsTableRow(
    "Grand Total",
    grandTotal,
    unmatchedGrandTotal,
    percentCompleteGrandTotal,
  );
  statsTableBody.appendChild(statsMoviesRow);
  statsTableBody.appendChild(statsSeriesRow);
  statsTableBody.appendChild(statsSeasonsRow);
  if (!disableCollections) {
    statsTableBody.appendChild(statsCollectionsRow);
  }
  statsTableBody.appendChild(statsGrandTotalRow);

  unmatchedAssets.movies.forEach((movie) => {
    const row = addTableRow(movie.title);
    movieTableBody.appendChild(row);
  });

  if (!disableCollections) {
    unmatchedAssets.collections.forEach((collection) => {
      const row = addTableRow(collection.title);
      collectionTableBody.appendChild(row);
    });
    collectionTableBody.style.display = "";
  } else {
    collectionTableBody.style.display = "none";
  }
  unmatchedAssets.shows.forEach((show) => {
    const mainPosterMissing = show.main_poster_missing ? "poster" : null;
    const seasonsArray = show.seasons.map((seasonObj) => seasonObj.season);
    const row = addTableRow(show.title, mainPosterMissing, seasonsArray);
    seriesTableBody.appendChild(row);
  });
}

function toggleSeasonList(seasonList) {
  if (seasonList.classList.contains("active")) {
    seasonList.classList.remove("active");
  } else {
    seasonList.classList.add("active");
  }
}

function populateTab(tabName, files) {
  const tabContent = document.getElementById(`${tabName}-content`);
  tabContent.innerHTML = "";

  const tabInner = document.createElement("div");
  tabInner.classList.add("tab-inner");
  if (typeof files === "object" && !Array.isArray(files)) {
    files = Object.values(files);
  }
  files.forEach((file) => {
    if (tabName === "series" || (file.seasons && Array.isArray(file.seasons))) {
      const showFile = createFileLink(
        file.file_path,
        file.source_path,
        file.file_name,
      );

      const seasonList = document.createElement("ul");
      seasonList.classList.add("season-list");

      file.seasons.forEach((season) => {
        const seasonItem = createFileLink(
          season.file_path,
          season.source_path,
          null,
          season,
          true,
        );
        seasonList.appendChild(seasonItem);
        seasonItem.addEventListener("click", (event) => {
          event.stopPropagation();
        });
      });
      showFile.addEventListener("click", () => toggleSeasonList(seasonList));
      showFile.appendChild(seasonList);
      tabInner.appendChild(showFile);
    } else {
      const mediaFile = createFileLink(
        file.file_path,
        file.source_path,
        file.file_name,
      );
      tabInner.appendChild(mediaFile);
    }
  });
  tabContent.appendChild(tabInner);
}

function createFileLink(
  filePath,
  sourcePath,
  displayName = null,
  seasonData = null,
  isSeasonLink = false,
) {
  const listItem = document.createElement("li");
  const fileName = document.createElement("span");
  listItem.dataset.sourcePath = sourcePath;
  listItem.classList.add("file-link");

  if (isSeasonLink) {
    listItem.onclick = () => previewImage(filePath, listItem, isSeasonLink);
    const seasonText =
      seasonData.season === 0 ? "Specials" : `Season ${seasonData.season}`;
    fileName.textContent = seasonText;
  } else {
    listItem.onclick = () => previewImage(filePath, listItem);
    fileName.textContent = displayName;
  }
  listItem.appendChild(fileName);
  return listItem;
}

function previewImage(filePath, fileLink, isSeasonLink = false) {
  const previewContainer = document.getElementById("image-preview-container");
  previewContainer.innerHTML = "";
  const previewDiv = document.createElement("div");
  previewDiv.classList.add("preview-div");

  const allLinks = document.querySelectorAll(".file-link");
  allLinks.forEach((link) => {
    link.classList.remove("active");
  });
  fileLink.classList.add("active");
  if (!isSeasonLink) {
    const allSeasonLists = document.querySelectorAll(".season-list.active");
    allSeasonLists.forEach((list) => {
      list.classList.remove("active");
    });
  }

  const imageSourcePath = document.createElement("p");
  imageSourcePath.classList.add("image-metadata");

  if (filePath === "") {
    imageSourcePath.textContent = "Poster not found";
    previewDiv.appendChild(imageSourcePath);
    return;
  }

  const imageDiv = document.createElement("div");
  imageDiv.classList.add("image-div");
  const imgElement = document.createElement("img");
  imgElement.src = filePath;
  imgElement.alt = "Preview Image";
  imageDiv.appendChild(imgElement);

  const sourcePath = fileLink.dataset.sourcePath;
  const parts = sourcePath.split("/");
  const parentDir = parts[parts.length - 2];
  const fileName = parts[parts.length - 1];

  const firstPart = document.createTextNode(parts.slice(0, -2).join("/") + "/");
  const parentDirPart = document.createElement("span");
  parentDirPart.classList.add("bold-text");
  parentDirPart.textContent = parentDir;

  const fileNamePart = document.createTextNode("/" + fileName);

  const plexUploadRunProgress = createRunProgress(
    "run-plex-uploader",
    "plex-upload-progress",
    "RUN PLEX UPLOADERR",
  );
  const plexUploadRunButton = plexUploadRunProgress.querySelector("button");
  attachRunListener(
    plexUploadRunButton,
    "/run-plex-upload-job",
    "PLEX UPLOADERR",
    "plex-upload-progress",
  );

  imageSourcePath.appendChild(firstPart);
  imageSourcePath.appendChild(parentDirPart);
  imageSourcePath.appendChild(fileNamePart);

  previewDiv.appendChild(imageDiv);
  previewDiv.appendChild(imageSourcePath);
  previewDiv.appendChild(plexUploadRunProgress);
  previewContainer.appendChild(previewDiv);
}

function createTabGroup() {
  const tabContainer = document.createElement("div");
  tabContainer.classList.add("tab-container");
  const tabs = ["all", "movies", "series", "collections"];
  const tabButtonsContainer = document.createElement("div");
  tabButtonsContainer.classList.add("tab-buttons-container");

  tabs.forEach((tab) => {
    const tabButton = document.createElement("button");
    tabButton.classList.add("tab-links");
    tabButton.textContent = tab.charAt(0).toUpperCase() + tab.slice(1);
    tabButton.onclick = function (event) {
      openTab(event, tab);
    };
    tabButtonsContainer.appendChild(tabButton);
  });
  const tabSearchBar = document.createElement("input");
  tabSearchBar.classList.add("tab-search");
  tabSearchBar.id = "tab-search";
  tabSearchBar.type = "text";
  tabSearchBar.placeholder = "Search...";
  tabSearchBar.addEventListener("keyup", function () {
    filterTabContent();
  });

  tabContainer.appendChild(tabButtonsContainer);
  tabContainer.appendChild(tabSearchBar);
  return tabContainer;
}

function filterTabContent() {
  const searchBar = document.getElementById("tab-search");
  const filter = searchBar.value.toLowerCase();
  const activeTabContent = document.querySelector(".tab-content.active");
  if (activeTabContent) {
    const items = activeTabContent.querySelectorAll(
      ".file-link:not(.season-list .file-link)",
    );

    items.forEach((item) => {
      const text = item.querySelector("span").textContent;
      if (text.toLowerCase().indexOf(filter) > -1) {
        item.style.display = "";
      } else {
        item.style.display = "none";
      }
    });
  }
}

function createTabContent() {
  const tabs = ["all", "movies", "series", "collections"];
  const tabContents = [];

  tabs.forEach((tab) => {
    const tabContent = document.createElement("div");
    tabContent.classList.add("tab-content");
    tabContent.id = `${tab}-content`;
    tabContents.push(tabContent);
  });
  return tabContents;
}

function openTab(evt, tabName) {
  const tabContent = document.getElementsByClassName("tab-content");
  for (let i = 0; i < tabContent.length; i++) {
    tabContent[i].classList.remove("active");
  }
  const tabLinks = document.getElementsByClassName("tab-links");
  for (let i = 0; i < tabLinks.length; i++) {
    tabLinks[i].classList.remove("active");
  }
  const currentTabContent = document.getElementById(`${tabName}-content`);
  currentTabContent.classList.add("active");

  const unmatchedTables = document.getElementsByClassName("unmatched-wrapper");
  for (let i = 0; i < unmatchedTables.length; i++) {
    unmatchedTables[i].classList.remove("active");
  }

  const currentUnmatchedContent = document.getElementById(
    `unmatched-${tabName}`,
  );
  const unmatchedProgressDiv = document.getElementById("unmatchedProgressDiv");
  unmatchedProgressDiv.classList.remove("active");

  if (
    currentUnmatchedContent &&
    currentUnmatchedContent.querySelector("tbody").children.length > 0
  ) {
    currentUnmatchedContent.classList.add("active");
    unmatchedProgressDiv.classList.add("active");
  }

  evt.currentTarget.classList.add("active");
  filterTabContent();
}

function createPosterRenamerBox() {
  const fileBrowserDiv = document.getElementById("file-browser-container");
  fileBrowserDiv.classList.add("file-browser");
  const unmatchedContainer = document.getElementById("unmatched-container");

  const tabGroup = createTabGroup();
  const tabContents = createTabContent();

  const posterRenamerRunProgress = createRunProgress(
    "run-renamer",
    "poster-renamer-progress",
    "RUN RENAMERR",
  );
  const posterRenamerRunButton =
    posterRenamerRunProgress.querySelector("button");
  attachRunListener(
    posterRenamerRunButton,
    "/run-renamer-job",
    "POSTER RENAMERR",
    "poster-renamer-progress",
  );

  createAllUnmatchedTables();
  const unmatchedRunProgress = createRunProgress(
    "run-unmatched",
    "unmatched-progress",
    "RUN UNMATCHED ASSETS",
  );
  unmatchedRunProgress.id = "unmatchedProgressDiv";
  unmatchedRunProgress.classList.add("unmatched-progress");
  const unmatchedRunButton = unmatchedRunProgress.querySelector("button");
  attachRunListener(
    unmatchedRunButton,
    "/run-unmatched-job",
    "UNMATCHED ASSETS",
    "unmatched-progress",
  );

  fileBrowserDiv.appendChild(tabGroup);
  tabContents.forEach((div) => {
    fileBrowserDiv.appendChild(div);
  });

  fileBrowserDiv.appendChild(posterRenamerRunProgress);
  unmatchedContainer.appendChild(unmatchedRunProgress);
}

function createRunProgress(buttonId, progressId, buttonText) {
  const progressRunDiv = document.createElement("div");
  progressRunDiv.classList.add("progress-run-div");
  const progressContainer = document.createElement("div");
  progressContainer.classList.add("progress");

  const runButton = document.createElement("button");
  runButton.classList.add("btn", "btn-primary", "btn-run");
  runButton.id = buttonId;
  runButton.textContent = buttonText;

  const progressBar = document.createElement("div");
  progressBar.id = progressId;
  progressBar.classList.add("progress-bar");

  progressContainer.appendChild(progressBar);
  progressRunDiv.appendChild(progressContainer);
  progressRunDiv.appendChild(runButton);
  return progressRunDiv;
}

function attachRunListener(button, jobRoute, jobName, progressId) {
  button.addEventListener("click", function () {
    button.disabled = true;
    button.textContent = "RUNNING";
    fetch(jobRoute, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.job_id) {
          console.log("Job started", data);
          const jobId = data.job_id;
          checkProgress(jobId, button, progressId, jobName);
        } else {
          console.error("Job ID missing from response", data);
          button.disabled = false;
          button.textContent = `RUN ${jobName}`;
        }
      })
      .catch((error) => {
        console.error("Error starting job", error);
        button.disabled = false;
        button.textContent = `RUN ${jobName}`;
      });
  });
}

function checkProgress(jobId, button, progressId, jobName) {
  fetch(`/progress/${jobId}`)
    .then((response) => response.json())
    .then((data) => {
      const progress = parseInt(data.value) || 0;
      const state = data.state || "Pending";
      const progressBar = document.getElementById(progressId);

      progressBar.style.width = progress + "%";
      progressBar.textContent = `${progress}%`;

      if (progress > 0) {
        progressBar.style.backgroundColor = "#4caf50";
      } else {
        progressBar.style.backgroundColor = "transparent";
      }

      if (state !== "Completed") {
        setTimeout(
          () => checkProgress(jobId, button, progressId, jobName),
          1000,
        );
      } else {
        console.log("Job Complete");
        progressBar.textContent = "100%";
        button.disabled = false;
        button.textContent = `RUN ${jobName}`;
      }
    })
    .catch((error) => {
      console.error("Error checking progress", error);
      button.disabled = false;
      button.textContent = `RUN ${jobName}`;
    });
}
