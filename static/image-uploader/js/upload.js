// static/image-uploader/js/upload.js

document.addEventListener('DOMContentLoaded', () => {
    const fileUpload = document.getElementById('file-upload');
    const imagesButton = document.getElementById('images-tab-btn');
    const dropzone = document.querySelector('.upload__dropzone');
    const currentUploadInput = document.querySelector('.upload__input');
    const copyButton = document.querySelector('.upload__copy');

    // Update active tab style
    const updateTabStyles = () => {
        const uploadTab = document.getElementById('upload-tab-btn');
        const imagesTab = document.getElementById('images-tab-btn');
        const isImagesPage = window.location.pathname.includes('images.html');
        uploadTab.classList.remove('upload__tab--active');
        imagesTab.classList.remove('upload__tab--active');
        if (isImagesPage) {
            imagesTab.classList.add('upload__tab--active');
        } else {
            uploadTab.classList.add('upload__tab--active');
        }
    };

    // Save file info to localStorage
    const storeFileInLocalStorage = (filename) => {
        const storedFiles = JSON.parse(localStorage.getItem('uploadedImages')) || [];
        if (!storedFiles.some(f => f.name === filename)) {
            storedFiles.push({ name: filename });
            localStorage.setItem('uploadedImages', JSON.stringify(storedFiles));
        }
    };

    // Upload file to backend server
    const uploadFileToServer = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok && data.status === 'success') {
            const filename = data.filename;
            const fullUrl = `http://localhost:8080/images/${filename}`;
            storeFileInLocalStorage(filename);
            if (currentUploadInput) {
                currentUploadInput.value = fullUrl;
            }
            alert(`File "${file.name}" uploaded successfully!`);
        } else {
           
            if (response.status === 415) {
                alert(`Error: File content is not a valid image. Only JPEG, PNG, GIF are allowed.`);
            } else {
                
                const errorMsg = data.message || 'Unknown error';
                alert(`Error: ${errorMsg}`);
            }
        }
    } catch (error) {
        console.error('Upload error:', error);
        alert('Failed to upload file. Please check your connection to the server.');
    }
};

    // Handle selected files (from button or drag&drop)
    const handleFiles = (files) => {
        if (!files || files.length === 0) return;

        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif'];
        const MAX_SIZE_MB = 5;
        const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

        for (const file of files) {
            if (!allowedTypes.includes(file.type)) {
                alert(`File "${file.name}" is not supported. Allowed: JPG, PNG, GIF.`);
                continue;
            }
            if (file.size > MAX_SIZE_BYTES) {
                alert(`File "${file.name}" exceeds ${MAX_SIZE_MB} MB limit.`);
                continue;
            }
            uploadFileToServer(file);
        }
    };

    // Event: file input change
    if (fileUpload) {
        fileUpload.addEventListener('change', (event) => {
            handleFiles(event.target.files);
            event.target.value = ''; // reset to allow re-upload of same file
        });
    }

    // Drag & drop events
    if (dropzone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        dropzone.addEventListener('drop', (event) => {
            handleFiles(event.dataTransfer.files);
        });
    }

    // Switch to Images tab
    if (imagesButton) {
        imagesButton.addEventListener('click', () => {
            window.location.href = 'images.html';
        });
    }

    // Copy URL to clipboard
    if (copyButton && currentUploadInput) {
        copyButton.addEventListener('click', () => {
            const textToCopy = currentUploadInput.value;
            if (textToCopy && textToCopy !== 'https://') {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    copyButton.textContent = 'COPIED!';
                    setTimeout(() => {
                        copyButton.textContent = 'COPY';
                    }, 2000);
                }).catch(err => console.error('Copy failed:', err));
            }
        });
    }

    updateTabStyles();
});