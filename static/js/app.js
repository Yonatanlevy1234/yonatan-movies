/* ===================================================
   Official Cinema Portal - Frontend Logic
   =================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const searchInput = document.getElementById('searchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    const tableSection = document.getElementById('tableSection');
    const moviesTableBody = document.getElementById('moviesTableBody');
    const loadingState = document.getElementById('loadingState');
    const initialState = document.getElementById('initialState');
    const emptyState = document.getElementById('emptyState');
    const displayedCount = document.getElementById('displayedCount');
    const totalMoviesBadge = document.getElementById('totalMoviesBadge');

    // Modal Player
    const videoModal = document.getElementById('videoModal');
    const videoPlayer = document.getElementById('videoPlayer');
    const videoSource = document.getElementById('videoSource');
    const modalMovieTitle = document.getElementById('modalMovieTitle');
    const modalMovieMeta = document.getElementById('modalMovieMeta');
    const modalDownloadLink = document.getElementById('modalDownloadLink');

    let allMovies = [];
    let searchTimeout = null;

    /**
     * Formats bytes into human readable format (MB / GB)
     */
    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '1.2 GB';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Fetches total count for header badge on startup
     */
    async function fetchStats() {
        try {
            const response = await fetch('/api/movies?limit=1');
            const data = await response.json();
            if (data.status === 'success') {
                totalMoviesBadge.textContent = `${data.total_count || 0} סרטים במאגר הערוץ`;
            }
        } catch (e) {
            console.error('Error fetching stats:', e);
            totalMoviesBadge.textContent = 'מחובר לערוץ';
        }
    }

    /**
     * Fetches movie search results from FastAPI backend
     */
    async function loadMovies(query = '') {
        const trimmed = query.trim();
        
        if (!trimmed) {
            showInitialState();
            return;
        }

        showLoading();
        try {
            const url = `/api/search?q=${encodeURIComponent(trimmed)}`;
            const response = await fetch(url);
            const data = await response.json();

            if (data.status === 'success') {
                const movies = data.movies || [];
                allMovies = movies;
                renderTableRows(movies);
                if (data.total_count) {
                    totalMoviesBadge.textContent = `${data.total_count} סרטים במאגר הערוץ`;
                }
            } else {
                showEmpty();
            }
        } catch (error) {
            console.error('Error fetching movies:', error);
            showEmpty();
        }
    }

    /**
     * Renders text-only movie rows in table
     */
    function renderTableRows(movies) {
        moviesTableBody.innerHTML = '';
        displayedCount.textContent = movies.length;

        if (movies.length === 0) {
            showEmpty();
            return;
        }

        showResultsTable();

        movies.forEach((movie, index) => {
            const tr = document.createElement('tr');
            const formattedSize = formatBytes(movie.file_size);
            const formatStr = movie.mime_type ? movie.mime_type.split('/')[1].toUpperCase() : 'MP4';

            tr.innerHTML = `
                <td class="col-num">${index + 1}</td>
                <td class="col-title">${movie.title}</td>
                <td class="col-year"><span class="year-tag">${movie.year || 2024}</span></td>
                <td class="col-size">${formattedSize}</td>
                <td class="col-format"><span class="format-badge">${formatStr}</span></td>
                <td class="col-actions">
                    <div class="action-group">
                        <button class="btn btn-play" onclick="openPlayerModal(${movie.id})">
                            <i class="fa-solid fa-play"></i> צפייה
                        </button>
                        <a class="btn btn-download" href="/api/download/${movie.id}" target="_blank" download>
                            <i class="fa-solid fa-download"></i> הורדה
                        </a>
                    </div>
                </td>
            `;
            moviesTableBody.appendChild(tr);
        });
    }

    /**
     * Triggers manual scan of channel messages
     */
    window.syncChannel = async function() {
        const syncIcon = document.getElementById('syncIcon');
        if (syncIcon) syncIcon.classList.add('fa-spin');
        
        try {
            const res = await fetch('/api/sync', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                totalMoviesBadge.textContent = `${data.total_movies} סרטים במאגר הערוץ`;
                if (searchInput.value.trim()) {
                    await loadMovies(searchInput.value);
                }
            }
        } catch (e) {
            console.error('Error syncing channel:', e);
        } finally {
            if (syncIcon) syncIcon.classList.remove('fa-spin');
        }
    };

    /**
     * Opens HTML5 Video Modal for streaming
     */
    window.openPlayerModal = async function(movieId) {
        try {
            let movie = allMovies.find(m => m.id === movieId);
            if (!movie) {
                const res = await fetch(`/api/movies/${movieId}`);
                const data = await res.json();
                movie = data.movie;
            }

            if (!movie) return;

            modalMovieTitle.textContent = movie.title;
            modalMovieMeta.textContent = `שנת יציאה: ${movie.year || 2024} • גודל: ${formatBytes(movie.file_size)} • פורמט MP4`;
            modalDownloadLink.href = `/api/download/${movie.id}`;

            videoSource.src = `/api/stream/${movie.id}`;
            videoPlayer.load();

            videoModal.classList.add('active');
            videoPlayer.play().catch(err => {
                console.log('Autoplay deferred:', err);
            });
        } catch (e) {
            console.error('Error launching stream player:', e);
        }
    };

    /**
     * Closes Video Modal
     */
    window.closePlayerModal = function() {
        videoModal.classList.remove('active');
        videoPlayer.pause();
        videoSource.src = '';
        videoPlayer.load();
    };

    // Modal backdrop click listener
    videoModal.addEventListener('click', (e) => {
        if (e.target === videoModal) {
            closePlayerModal();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && videoModal.classList.contains('active')) {
            closePlayerModal();
        }
    });

    // Live search listener
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value;
        clearSearchBtn.hidden = !query;

        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            loadMovies(query);
        }, 300);
    });

    window.clearSearch = function() {
        searchInput.value = '';
        clearSearchBtn.hidden = true;
        showInitialState();
    };

    const statsSummary = document.getElementById('statsSummary');

    function showInitialState() {
        if (loadingState) loadingState.style.display = 'none';
        if (emptyState) emptyState.style.display = 'none';
        if (tableSection) tableSection.style.display = 'none';
        if (statsSummary) statsSummary.style.display = 'none';
        if (displayedCount) displayedCount.textContent = '0';
    }

    function showLoading() {
        if (loadingState) loadingState.style.display = 'block';
        if (emptyState) emptyState.style.display = 'none';
        if (tableSection) tableSection.style.display = 'none';
        if (statsSummary) statsSummary.style.display = 'none';
    }

    function showResultsTable() {
        if (loadingState) loadingState.style.display = 'none';
        if (emptyState) emptyState.style.display = 'none';
        if (tableSection) tableSection.style.display = 'block';
        if (statsSummary) statsSummary.style.display = 'block';
    }

    function showEmpty() {
        if (loadingState) loadingState.style.display = 'none';
        if (emptyState) emptyState.style.display = 'block';
        if (tableSection) tableSection.style.display = 'none';
        if (statsSummary) statsSummary.style.display = 'none';
        if (displayedCount) displayedCount.textContent = '0';
    }

    // Initial Startup
    fetchStats();
    showInitialState();
});
