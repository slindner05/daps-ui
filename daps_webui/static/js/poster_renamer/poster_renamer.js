document.addEventListener("DOMContentLoaded", function() {
    createPosterRenamerBox();
    document.querySelector(".tab-links").click();
});

fetch("/poster-renamer/get-file-paths")
    .then((response) => response.json())
    .then((data) => {
        if (data.success) {
            const sortedFiles = data.sorted_files;
            console.log(sortedFiles);
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
            tabContent.appendChild(showFile);
        } else {
            const mediaFile = createFileLink(
                file.file_path,
                file.source_path,
                file.file_name,
            );
            tabContent.appendChild(mediaFile);
        }
    });
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
    previewContainer.classList.add("content-box");

    const imgElement = document.createElement("img");
    imgElement.src = filePath;
    imgElement.alt = "Preview Image";
    previewContainer.appendChild(imgElement);

    const imageSourcePath = document.createElement("p");
    imageSourcePath.classList.add("image-metadata");
    const sourcePath = fileLink.dataset.sourcePath;
    const parts = sourcePath.split("/");
    const parentDir = parts[parts.length - 2];
    const fileName = parts[parts.length - 1];

    const firstPart = document.createTextNode(parts.slice(0, -2).join("/") + "/");
    const parentDirPart = document.createElement("span");
    parentDirPart.classList.add("red-text");
    parentDirPart.textContent = parentDir;

    const fileNamePart = document.createTextNode("/" + fileName);

    imageSourcePath.appendChild(firstPart);
    imageSourcePath.appendChild(parentDirPart);
    imageSourcePath.appendChild(fileNamePart);

    previewContainer.appendChild(imageSourcePath);

    const imageFileName = document.createElement("p");
    imageFileName.classList.add("image-metadata");
    imageFileName.textContent = filePath.split("/").pop();
    previewContainer.appendChild(imageFileName);

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
}

function createTabGroup() {
    const tabContainer = document.createElement("div");
    tabContainer.classList.add("tab-container");
    const tabs = ["all", "movies", "series", "collections"];
    tabs.forEach((tab) => {
        const tabButton = document.createElement("button");
        tabButton.classList.add("tab-links");
        tabButton.textContent = tab.charAt(0).toUpperCase() + tab.slice(1);
        tabButton.onclick = function(event) {
            openTab(event, tab);
        };
        tabContainer.appendChild(tabButton);
    });
    return tabContainer;
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
    console.log(evt.currentTarget);
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

    evt.currentTarget.classList.add("active");
}

function createPosterRenamerBox() {
    const fileBrowserContentBox = document.getElementById("content");
    const fileBrowserDiv = document.getElementById("file-browser-container");
    fileBrowserDiv.classList.add("file-browser");
    const imagePreviewDiv = document.getElementById("image-preview-container");
    imagePreviewDiv.classList.add("preview");
    const progressContainer = document.getElementById("progress-container");
    progressContainer.classList.add("progress");

    const tabGroup = createTabGroup();
    const tabContents = createTabContent();

    const posterRenamerRunButton = document.createElement("button");
    posterRenamerRunButton.classList.add("btn", "btn-primary", "btn-run");
    posterRenamerRunButton.id = "run-renamer";
    posterRenamerRunButton.textContent = "RUN";
    attachPosterRenamerRunListener(posterRenamerRunButton);

    const progressBar = document.createElement("div");
    progressBar.id = "poster-renamer-progress";
    progressBar.classList.add("progress-bar");

    progressContainer.appendChild(progressBar);

    fileBrowserDiv.appendChild(tabGroup);
    tabContents.forEach((div) => {
        fileBrowserDiv.appendChild(div);
    });

    fileBrowserContentBox.appendChild(progressContainer);
    fileBrowserContentBox.appendChild(posterRenamerRunButton);
}

function attachPosterRenamerRunListener(button) {
    button.addEventListener("click", function() {
        button.disabled = true;
        fetch(`/run-renamer-job`, {
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
                    checkProgress(jobId, button);
                } else {
                    console.error("Job ID missing from response", data);
                    button.disabled = false;
                }
            })
            .catch((error) => {
                console.error("Error starting job", error);
                button.disabled = false;
            });
    });
}

function checkProgress(jobId, button) {
    fetch(`/progress/${jobId}`)
        .then((response) => response.json())
        .then((data) => {
            const progress = data.value || 0;
            const state = data.state || "Pending";
            const progressBar = document.getElementById("poster-renamer-progress");
            progressBar.style.width = progress + "%";
            progressBar.textContent = progress + "%";

            if (progress > 0) {
                progressBar.style.backgroundColor = "#4caf50";
            } else {
                progressBar.style.backgroundColor = "transparent";
            }

            if (state !== "Completed") {
                setTimeout(() => checkProgress(jobId, button), 1000);
            } else {
                console.log("Job Complete");
                progressBar.textContent = "100%";
                button.disabled = false;
            }
        })
        .catch((error) => {
            console.error("Error checking progress", error);
            button.disabled = false;
        });
}
