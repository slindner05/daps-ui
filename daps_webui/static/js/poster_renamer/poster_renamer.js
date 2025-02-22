document.addEventListener("DOMContentLoaded", function () {
  createPosterRenamerBox();
  const fileBrowser = document.querySelector(".file-browser");
  if (fileBrowser) {
    setTimeout(() => {
      fileBrowser.classList.add("loaded");
    }, 100);
  }
  refreshSortedFiles(() => {
    clickFirstFileLink();
  });
  refreshUnmatched();
});

let activePosterIdentifier = null;
let activeSeriesIdentifier = null;

function saveActiveFileLink() {
  const activePoster = document.querySelector(".file-link.active");
  if (activePoster) {
    activePosterIdentifier = activePoster.getAttribute("data-identifier");

    const seasonList = activePoster.closest(".season-list.active");
    if (seasonList) {
      const seriesLink = seasonList.closest(".file-link");
      if (seriesLink) {
        activeSeriesIdentifier = seriesLink.getAttribute("data-identifier");
      }
    }
  }
  console.log("Active Poster Identifier:", activePosterIdentifier);
  console.log("Active Series Identifier:", activeSeriesIdentifier);
}

function clickFirstFileLink() {
  const firstTabLink = document.querySelector(".tab-links");
  const firstFileLink = document.querySelector(".file-link");
  if (firstTabLink && firstFileLink) {
    setTimeout(() => {
      firstTabLink.click();
      firstFileLink.click();
    }, 100);
  }
}

function clickActiveFileLink() {
  const activeTab = document.querySelector(".tab-content.active");
  if (!activeTab) {
    console.warn("No active tab found.");
    return;
  }
  const activeSeriesLink = null;
  if (activeSeriesIdentifier) {
    const activeSeriesLink = activeTab.querySelector(
      `.file-link[data-identifier="${activeSeriesIdentifier}"]`,
    );
    if (activeSeriesLink) {
      activeSeriesLink.scrollIntoView({
        behavior: "instant",
        block: "center",
      });
      setTimeout(() => {
        activeSeriesLink.click();
        console.log("Clicked series link for:", activeSeriesIdentifier);
      }, 200);
    } else {
      console.warn("Series link not found for:", activeSeriesIdentifier);
    }
  }
  if (activePosterIdentifier) {
    const activeFileLink = activeTab.querySelector(
      `.file-link[data-identifier="${activePosterIdentifier}"]`,
    );
    if (activeFileLink) {
      if (activeSeriesLink) {
        setTimeout(() => {
          activeFileLink.click();
        }, 200);
      } else {
        activeFileLink.scrollIntoView({
          behavior: "instant",
          block: "center",
        });
        setTimeout(() => {
          activeFileLink.click();
        }, 200);
      }
      console.log("Clicked active poster link for:", activePosterIdentifier);
    } else {
      console.warn("Active poster link not found for:", activeFileLink);
    }
  }
}

const routeMap = {
  renamer: "/poster-renamer/get-file-paths",
  unmatched: "/poster-renamer/unmatched",
  jobData: "/poster-renamer/job-data",
};

function refreshSortedFiles(callback) {
  const endpoint = routeMap.renamer;
  saveActiveFileLink();
  fetch(endpoint)
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        const sortedFiles = data.sorted_files;
        console.log(sortedFiles);

        const isSortedFilesEmpty =
          sortedFiles.movies.length === 0 &&
          Object.keys(sortedFiles.shows).length === 0 &&
          sortedFiles.collections.length === 0;

        const unmatchedContainer = document.getElementById(
          "unmatched-container",
        );
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
        if (callback && typeof callback == "function") {
          callback();
        }
      } else {
        console.error("Error fetching images: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error:", error);
    });
}

function refreshUnmatched() {
  const endpoint = routeMap.unmatched;
  fetch(endpoint)
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
      console.error("Error refreshing unmatched media:", error);
    });
}

function getJobData() {
  const endpoint = routeMap.jobData;
  fetch(endpoint)
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        console.log(data);
        const { jobs } = data;
        const { current_jobs, job_history } = jobs;
        Object.keys(current_jobs).forEach((jobKey) => {
          const jobDiv = document.querySelector(`[data-job-id="${jobKey}"]`);
          if (!jobDiv) {
            console.warn(`No job div found for: ${jobKey}`);
            return;
          }

          const historyDiv = jobDiv.querySelector(".job-history");
          if (!historyDiv) {
            console.warn(`No .job-history div found for: ${jobKey}`);
            return;
          }

          historyDiv.innerHTML = "";

          const jobInfo = current_jobs[jobKey] || {};

          const nextRunTimestamp = jobInfo.next_run || null;
          const lastRunTimestamp = jobInfo.last_run || null;

          const nextRunText = nextRunTimestamp
            ? formatExactDate(nextRunTimestamp, true)
            : "Not Scheduled";
          const lastRunText = lastRunTimestamp
            ? formatExactDate(lastRunTimestamp, false)
            : "Never";

          const nextRun = document.createElement("p");
          nextRun.innerHTML = `<i class= "fas fa-clock"></i><span class="badge">${nextRunText}</span>`;

          const lastRun = document.createElement("p");
          if (lastRunText === "Never") {
            lastRun.innerHTML = `<i class="fas fa-history"></i> <span class="badge">${lastRunText}</span>`;
          } else {
            lastRun.innerHTML = `<i class="fas fa-history"></i><button class="badge job-history-btn" data-job-key="${jobKey}">${lastRunText}</button>`;
          }
          historyDiv.appendChild(nextRun);
          historyDiv.appendChild(lastRun);
        });
        document.querySelectorAll(".job-history-btn").forEach((btn) => {
          btn.addEventListener("click", function () {
            const jobKey = this.getAttribute("data-job-key");
            openJobHistoryModal(jobKey, job_history[jobKey] || []);
          });
        });
      } else {
        console.error("Error fetching job data: " + data.message);
      }
    })
    .catch((error) => {
      console.error("Error fetching job data:", error);
    });
}
function openJobHistoryModal(jobKey, history) {
  const modal = document.getElementById("jobHistoryModal");
  const modalTitle = document.getElementById("modalTitle");
  const modalBody = document.getElementById("modalBody");
  const closeButton = modal.querySelector(".close");
  if (!closeButton.dataset.listenerAdded) {
    closeButton.addEventListener("click", closeModal);
    closeButton.dataset.listenerAdded = "true";
  }

  modalTitle.textContent = `Job history for ${jobKey}`;
  modalBody.innerHTML = "";
  if (history.length === 0) {
    modalBody.innerHTML = "<p>No history available.</p>";
  } else {
    const table = document.createElement("table");
    table.classList.add("job-history-table");
    table.innerHTML = `
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Run Type</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${history
          .map(
            (entry) => `
        <tr>
          <td>${formatExactDate(entry.run_time, false)}</td>
          <td>${entry.run_type}</td>
          <td>${entry.status}</td>
        </tr>`,
          )
          .join("")}
      </tbody>
    `;
    modalBody.appendChild(table);
  }
  modal.style.display = "block";
}

function closeModal() {
  document.getElementById("jobHistoryModal").style.display = "none";
}

window.onclick = function (event) {
  const modal = document.getElementById("jobHistoryModal");
  if (event.target === modal) {
    closeModal();
  }
};

function formatExactDate(timestamp, isFuture = false) {
  const utcDate = new Date(timestamp);
  const localDate = new Date(
    utcDate.getTime() + utcDate.getTimezoneOffset() * 60000,
  );
  const now = new Date();

  const diffInMs = Math.abs(localDate.getTime() - now.getTime());
  const diffInMinutes = Math.round(diffInMs / 60000);
  const diffInHours = Math.round(diffInMs / 3600000);
  const diffInDays = Math.round(diffInMs / 86400000);

  if (isFuture) {
    if (diffInMinutes < 1) return "Less than 1 minute";
    if (diffInMinutes < 60) return `In ${diffInMinutes} minutes`;
    if (diffInHours === 1) return "In 1 hour";
    if (diffInHours < 24)
      return `Today at ${localDate.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })}`;
    if (diffInDays === 1)
      return `Tomorrow at ${localDate.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })}`;
  } else {
    if (diffInMinutes < 1) return "Just Now";
    if (diffInMinutes < 60) return `${diffInMinutes} minutes ago`;
    if (diffInHours === 1) return "1 hour ago";
    if (diffInHours < 24)
      return `Yesterday at ${localDate.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      })}`;
    if (diffInDays === 1)
      return `Yesterday at ${localDate.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      })}`;
  }

  return localDate.toLocaleString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function refreshUpdatedImage(clickedIdentifier) {
  if (clickedIdentifier === activeSeriesIdentifier) {
    const seriesImage = document.querySelector(
      `.image-div img[data-identifier="${activeSeriesIdentifier}"]`,
    );
    if (seriesImage) {
      const seriesCurrentSrc = seriesImage.src.split("?")[0];
      const seriesNewSrc = `${seriesCurrentSrc}?t=${new Date().getTime()}`;
      seriesImage.src = seriesNewSrc;
      console.log("Series poster refreshed:", seriesNewSrc);
    } else {
      console.warn("Series poster not found:", activeSeriesIdentifier);
    }
  } else if (clickedIdentifier === activePosterIdentifier) {
    const image = document.querySelector(
      `.image-div img[data-identifier="${activePosterIdentifier}"]`,
    );
    if (image) {
      const currentSrc = image.src.split("?")[0];
      const newSrc = `${currentSrc}?t=${new Date().getTime()}`;
      image.src = newSrc;
      console.log("Active poster refreshed:", newSrc);
    } else {
      console.warn("Active poster not found:", activePosterIdentifier);
    }
  }
}

function addFileLinkListeners() {
  if (activeSeriesIdentifier) {
    const seriesFileLinks = document.querySelectorAll(
      `.file-link[data-identifier="${activeSeriesIdentifier}"]`,
    );
    if (seriesFileLinks.length > 0) {
      seriesFileLinks.forEach((link) => {
        link.removeEventListener("click", refreshUpdatedImage);
        link.addEventListener("click", () =>
          refreshUpdatedImage(activeSeriesIdentifier),
        );
      });
      console.log(
        "Listeners added for series posters:",
        activeSeriesIdentifier,
      );
    } else {
      console.warn("File links not found for:", activeSeriesIdentifier);
    }
  }

  const refreshedFileLinks = document.querySelectorAll(
    `.file-link[data-identifier="${activePosterIdentifier}"]`,
  );
  if (refreshedFileLinks.length > 0) {
    refreshedFileLinks.forEach((link) => {
      link.removeEventListener("click", refreshUpdatedImage);
      link.addEventListener("click", () =>
        refreshUpdatedImage(activePosterIdentifier),
      );
    });
    console.log("Listeners added for active posters:", activePosterIdentifier);
  } else {
    console.warn("File links not found for:", activePosterIdentifier);
  }
}

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
  const identifier = filePath === "" ? displayName : filePath;
  const listItem = document.createElement("li");
  const fileName = document.createElement("span");
  listItem.setAttribute("data-identifier", identifier);
  listItem.dataset.sourcePath = sourcePath;
  listItem.classList.add("file-link");

  if (isSeasonLink) {
    listItem.onclick = () =>
      previewImage(filePath, listItem, identifier, isSeasonLink);
    const seasonText =
      seasonData.season === 0 ? "Specials" : `Season ${seasonData.season}`;
    fileName.textContent = seasonText;
  } else {
    listItem.onclick = () => previewImage(filePath, listItem, identifier);
    fileName.textContent = displayName;
  }
  listItem.appendChild(fileName);
  return listItem;
}

function previewImage(filePath, fileLink, identifier, isSeasonLink = false) {
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

  const placeholderImagePath = "/static/images/placeholders/no-image.jpg";
  const imageDiv = document.createElement("div");
  imageDiv.classList.add("image-div");
  const imgElement = document.createElement("img");
  if (filePath === "") {
    imgElement.src = placeholderImagePath;
    imgElement.alt = "No Image Available";
  } else {
    imgElement.src = filePath;
    imgElement.alt = "Preview Image";
  }
  imgElement.setAttribute("data-identifier", identifier);
  imgElement.onload = () => {
    previewDiv.classList.add("loaded");
  };
  imgElement.onerror = () => {
    console.warn("Failed to load image:", filePath);
  };
  imageDiv.appendChild(imgElement);

  const deleteButton = document.createElement("button");
  deleteButton.classList.add("delete-button");
  deleteButton.title = "Delete Poster";

  const trashIcon = document.createElement("i");
  trashIcon.classList.add("fas", "fa-trash");
  deleteButton.appendChild(trashIcon);

  if (filePath) {
    deleteButton.onclick = () => {
      if (confirm("Are you sure you want to delete this poster?")) {
        fetch("/delete-poster", {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ filePath }),
        })
          .then((response) => {
            if (response.ok) {
              refreshSortedFiles(() => {
                const firstFileLink = document.querySelector(".file-link");
                if (firstFileLink) {
                  firstFileLink.click();
                }
                const runUnmatchedButton =
                  document.getElementById("run-unmatched");
                if (runUnmatchedButton) {
                  runUnmatchedButton.click();
                  toggleDeleteButtons(deleteButton);
                  filterTabContent();
                }
              });
            } else {
              response.text().then((text) => alert(`Error: ${text}`));
            }
          })
          .catch((error) => {
            alert(`Request failed ${error}`);
          });
      }
    };
    imageDiv.appendChild(deleteButton);

    const runUnmatchedButton = document.getElementById("run-unmatched");
    const runRenamerButton = document.getElementById("run-renamer");
    if (runUnmatchedButton || runRenamerButton) {
      const observer = new MutationObserver(() => {
        toggleDeleteButtons(deleteButton);
      });
      if (runRenamerButton) {
        observer.observe(runRenamerButton, {
          attributes: true,
          attributeFilter: ["disabled"],
        });
      }
      if (runUnmatchedButton) {
        observer.observe(runUnmatchedButton, {
          attributes: true,
          attributeFilter: ["disabled"],
        });
      }
      if (
        (runUnmatchedButton && runUnmatchedButton.disabled) ||
        (runRenamerButton && runRenamerButton.disabled)
      ) {
        deleteButton.disabled = true;
        deleteButton.classList.add("disabled");
      } else {
        deleteButton.disabled = false;
        deleteButton.classList.remove("disabled");
      }
    }
  }

  const imageSourcePathDiv = document.createElement("div");
  imageSourcePathDiv.classList.add("image-source-div");
  const imageSourcePath = document.createElement("p");
  imageSourcePath.classList.add("image-metadata");

  const sourcePath = fileLink.dataset.sourcePath;
  const parts = sourcePath.split("/");
  const parentDir = parts[parts.length - 2];
  const fileName = parts[parts.length - 1];

  const parentDirPart = document.createElement("span");
  parentDirPart.classList.add("bold-text");
  parentDirPart.textContent = parentDir;

  const fileNamePart = document.createTextNode("/" + fileName);
  imageSourcePath.appendChild(parentDirPart);
  imageSourcePath.appendChild(fileNamePart);
  imageSourcePathDiv.appendChild(imageSourcePath);

  const plexUploadRunProgress = createRunProgress(
    "run-plex-uploader",
    "plex-upload-progress",
    "RUN PLEX UPLOADERR",
    "plex_uploaderr",
  );
  const plexUploadRunButton = plexUploadRunProgress.querySelector("button");
  attachRunListener(
    plexUploadRunButton,
    "/run-plex-upload-job",
    "PLEX UPLOADERR",
    "plex-upload-progress",
  );
  const borderReplaceRunProgress = createRunProgress(
    "run-border-replacer",
    "border-replace-progress",
    "RUN BORDER REPLACERR",
    "border_replacerr",
  );
  const borderReplaceRunButton =
    borderReplaceRunProgress.querySelector("button");
  attachRunListener(
    borderReplaceRunButton,
    "/run-border-replace-job",
    "BORDER REPLACERR",
    "border-replace-progress",
  );

  previewDiv.appendChild(imageDiv);
  if (filePath) {
    previewDiv.appendChild(imageSourcePathDiv);
  }
  previewDiv.appendChild(plexUploadRunProgress);
  previewDiv.appendChild(borderReplaceRunProgress);
  previewContainer.appendChild(previewDiv);
  getJobData();
}

function toggleDeleteButtons(deleteButton) {
  const runUnmatchedButton = document.getElementById("run-unmatched");
  const runRenamerButton = document.getElementById("run-renamer");
  if (
    (runUnmatchedButton && runUnmatchedButton.disabled) ||
    (runRenamerButton && runRenamerButton.disabled)
  ) {
    deleteButton.disabled = true;
    deleteButton.classList.add("disabled");
  } else {
    deleteButton.disabled = false;
    deleteButton.classList.remove("disabled");
  }
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
  const driveSyncProgressDiv = document.getElementById("driveSyncProgressDiv");
  driveSyncProgressDiv.classList.remove("active");

  if (
    currentUnmatchedContent &&
    currentUnmatchedContent.querySelector("tbody").children.length > 0
  ) {
    currentUnmatchedContent.classList.add("active");
    unmatchedProgressDiv.classList.add("active");
    driveSyncProgressDiv.classList.add("active");
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
    "poster_renamerr",
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
    "unmatched_assets",
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

  const driveSyncRunProgress = createRunProgress(
    "run-drive-sync",
    "drive-sync-progress",
    "RUN DRIVE SYNC",
    "drive_sync",
  );
  driveSyncRunProgress.id = "driveSyncProgressDiv";
  driveSyncRunProgress.classList.add("drive-sync-progress");
  const driveSyncRunButton = driveSyncRunProgress.querySelector("button");
  attachRunListener(
    driveSyncRunButton,
    "/run-drive-sync-job",
    "DRIVE SYNC",
    "drive-sync-progress",
  );

  fileBrowserDiv.appendChild(tabGroup);
  tabContents.forEach((div) => {
    fileBrowserDiv.appendChild(div);
  });

  fileBrowserDiv.appendChild(posterRenamerRunProgress);
  unmatchedContainer.appendChild(unmatchedRunProgress);
  unmatchedContainer.appendChild(driveSyncRunProgress);
}

function createRunProgress(buttonId, progressId, buttonText, jobIdentifier) {
  const progressRunDiv = document.createElement("div");
  progressRunDiv.classList.add("progress-run-div");
  progressRunDiv.setAttribute("data-job-id", jobIdentifier);

  const progressContainer = document.createElement("div");
  progressContainer.classList.add("progress");

  const runButton = document.createElement("button");
  runButton.classList.add("btn", "btn-primary", "btn-run");
  runButton.id = buttonId;
  runButton.textContent = buttonText;

  const progressBar = document.createElement("div");
  progressBar.id = progressId;
  progressBar.classList.add("progress-bar");

  const jobHistoryDiv = document.createElement("div");
  jobHistoryDiv.classList.add("job-history");
  jobHistoryDiv.id = `history-${jobIdentifier}`;

  const nextRun = document.createElement("p");
  nextRun.innerHTML = `<i class= "fas fa-clock"></i><span class="badge">Not Scheduled</span>`;

  const lastRun = document.createElement("p");
  lastRun.innerHTML = `<i class="fas fa-history"></i><span class="badge">Never</span>`;
  jobHistoryDiv.appendChild(nextRun);
  jobHistoryDiv.appendChild(lastRun);

  progressContainer.appendChild(progressBar);
  progressRunDiv.appendChild(progressContainer);
  progressRunDiv.appendChild(runButton);
  progressRunDiv.appendChild(jobHistoryDiv);

  return progressRunDiv;
}

function attachRunListener(button, jobRoute, jobName, progressId) {
  button.addEventListener("click", function () {
    button.disabled = true;
    button.classList.add("disabled");
    button.textContent = "RUNNING";
    fetch(jobRoute, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success && data.message) {
          if (data.job_id) {
            console.log("Job started", data);
            const jobId = data.job_id;
            checkProgress(jobId, button, progressId, jobName, jobRoute);
          } else {
            console.warn("Task skipped:", data.message);
            alert(data.message);
            button.disabled = false;
            button.classList.remove("disabled");
            button.textContent = `RUN ${jobName}`;
          }
        } else {
          console.error("Unexpected response", data);
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

function checkProgress(jobId, button, progressId, jobName, jobRoute) {
  const progressBar = document.getElementById(progressId);
  fetch(`/progress/${jobId}`)
    .then((response) => response.json())
    .then((data) => {
      const progress = parseInt(data.value) || 0;
      const state = data.state || "Pending";

      progressBar.style.width = progress + "%";
      progressBar.textContent = `${progress}%`;

      if (progress > 0) {
        progressBar.style.backgroundColor = "#4caf50";
      } else {
        progressBar.style.backgroundColor = "transparent";
      }

      if (state !== "Completed") {
        setTimeout(
          () => checkProgress(jobId, button, progressId, jobName, jobRoute),
          500,
        );
      } else {
        console.log("Job Complete");
        progressBar.textContent = "100%";
        refreshUI(jobRoute);
        setTimeout(() => {
          button.disabled = false;
          button.classList.remove("disabled");
          button.textContent = `RUN ${jobName}`;
          progressBar.style.width = "0%";
          progressBar.textContent = "";
          progressBar.style.backgroundColor = "transparent";
        }, 3000);
      }
    })
    .catch((error) => {
      console.error("Error checking progress", error);
      button.disabled = false;
      button.classList.remove("disabled");
      button.textContent = `RUN ${jobName}`;
    });
}

function refreshUI(jobRoute) {
  switch (jobRoute) {
    case "/run-unmatched-job":
      refreshUnmatched();
      getJobData();
      break;
    case "/run-plex-upload-job":
      getJobData();
      break;
    case "/run-drive-sync-job":
      getJobData();
      break;
    case "/run-renamer-job":
      refreshSortedFiles(() => {
        filterTabContent();
        addFileLinkListeners();
        clickActiveFileLink();
        refreshUnmatched();
        getJobData();
      });
      break;
    case "/run-border-replace-job":
      refreshSortedFiles(() => {
        filterTabContent();
        addFileLinkListeners();
        clickActiveFileLink();
        getJobData();
      });
      break;
    default:
      console.warn("No refresh function defined for:", jobRoute);
  }
}
