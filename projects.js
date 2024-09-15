// Initialize empty project list
var projects = JSON.parse(localStorage.getItem('projects')) || [];

// Function to save projects to localStorage
function saveProjects() {
    localStorage.setItem('projects', JSON.stringify(projects));
}

// Function to render projects
function renderProjects() {
    var projectList = document.getElementById('project-list');
    projectList.innerHTML = '';
    projects.forEach(function(project, index) {
        var li = document.createElement('li');
        li.innerHTML = `
            <h4>${project.name}</h4>
            <p>${project.description}</p>
            <p>Word Count: ${project.wordCount || 0}</p>
            <p>Deadline: ${project.deadline || 'No deadline'}</p>
            <button onclick="editProject(${index})">Edit</button>
            <button onclick="deleteProject(${index})">Delete</button>
        `;
        projectList.appendChild(li);
    });
}

// Function to add a new project
document.getElementById('add-project-btn').addEventListener('click', function() {
    document.getElementById('project-form').style.display = 'block';
});

// Function to save a new project
document.getElementById('save-project-btn').addEventListener('click', function() {
    var name = document.getElementById('project-name').value;
    var description = document.getElementById('project-description').value;
    var deadline = document.getElementById('project-deadline').value;
    
    if (name && description) {
        projects.push({ name: name, description: description, deadline: deadline, wordCount: 0 });
        saveProjects();
        renderProjects();
        document.getElementById('project-form').style.display = 'none';
        document.getElementById('project-name').value = '';
        document.getElementById('project-description').value = '';
        document.getElementById('project-deadline').value = '';
    }
});

// Function to cancel project creation
document.getElementById('cancel-project-btn').addEventListener('click', function() {
    document.getElementById('project-form').style.display = 'none';
});

// Function to edit a project
function editProject(index) {
    var project = projects[index];
    document.getElementById('project-name').value = project.name;
    document.getElementById('project-description').value = project.description;
    document.getElementById('project-deadline').value = project.deadline;
    document.getElementById('save-project-btn').innerText = 'Update Project';
    document.getElementById('save-project-btn').onclick = function() {
        project.name = document.getElementById('project-name').value;
        project.description = document.getElementById('project-description').value;
        project.deadline = document.getElementById('project-deadline').value;
        saveProjects();
        renderProjects();
        document.getElementById('project-form').style.display = 'none';
        document.getElementById('save-project-btn').innerText = 'Save Project';
        document.getElementById('save-project-btn').onclick = addNewProject;
    };
    document.getElementById('project-form').style.display = 'block';
}

// Function to delete a project
function deleteProject(index) {
    projects.splice(index, 1);
    saveProjects();
    renderProjects();
}

// Function to add a word count update
function updateWordCount(index, wordCount) {
    projects[index].wordCount = wordCount;
    saveProjects();
    renderProjects();
}

// Function to render achievements (basic version)
function renderAchievements() {
    var achievementsList = document.getElementById('achievements-list');
    achievementsList.innerHTML = '';

    projects.forEach(function(project) {
        if (project.wordCount >= 2000) {
            var li = document.createElement('li');
            li.textContent = `Project "${project.name}" reached 2000 words! 🎉`;
            achievementsList.appendChild(li);
        }
    });
}

// Initial render
renderProjects();
renderAchievements();
