document.addEventListener('DOMContentLoaded', () => {
    const dropzone = document.querySelector('.dropzone');
    const fileInput = document.getElementById('file-input');
    const convertBtn = document.querySelector('.convert-btn');
    const tabs = document.querySelectorAll('.tab');
    let currentConversionType = 'pdf-to-img';

    // Tab switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentConversionType = tab.dataset.type;
            updateDropzoneText();
        });
    });

    // Dropzone functionality
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    function handleFiles(files) {
        if (files.length === 0) return;

        const file = files[0];
        const validTypes = currentConversionType === 'pdf-to-img' 
            ? ['application/pdf']
            : ['image/jpeg', 'image/png'];

        if (!validTypes.includes(file.type)) {
            showError('Invalid file type');
            return;
        }

        if (file.size > 16 * 1024 * 1024) { // 16MB limit
            showError('File size too large');
            return;
        }

        updateDropzoneWithFile(file);
        convertBtn.disabled = false;
    }

    function updateDropzoneWithFile(file) {
        const dropzoneContent = dropzone.querySelector('.dropzone-content');
        dropzoneContent.innerHTML = `
            <p class="file-name">${file.name}</p>
            <p class="small">${formatFileSize(file.size)}</p>
        `;
    }

    function updateDropzoneText() {
        const dropzoneContent = dropzone.querySelector('.dropzone-content');
        const acceptedTypes = currentConversionType === 'pdf-to-img' ? 'PDF' : 'JPG, PNG';
        dropzoneContent.innerHTML = `
            <img src="/static/img/upload.svg" alt="Upload">
            <p>Drag & drop your ${acceptedTypes} file here or <span class="browse">browse</span></p>
            <p class="small">Supported formats: ${acceptedTypes}</p>
        `;
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);
        setTimeout(() => errorDiv.remove(), 3000);
    }

    // Convert button functionality
    convertBtn.addEventListener('click', async () => {
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('type', currentConversionType);

        try {
            convertBtn.disabled = true;
            convertBtn.textContent = 'Converting...';

            const response = await fetch('/convert', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.error) {
                showError(data.error);
                if (data.error === 'Daily conversion limit reached') {
                    window.location.href = '/subscribe';
                }
            } else {
                window.location.href = data.download_url;
            }
        } catch (error) {
            showError('Conversion failed. Please try again.');
        } finally {
            convertBtn.disabled = false;
            convertBtn.textContent = 'Convert Now';
            fileInput.value = '';
            updateDropzoneText();
        }
    });
});
