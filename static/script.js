// Expose global functions for popup and modal actions
window.selectStyle = selectStyle;
window.closeModal = closeModal;

// Global variable to hold the last search query
let lastQuery = "";

/**
 * Close the diamond details modal
 */
function closeModal() {
  document.getElementById("detailsModal").style.display = "none";
}

/**
 * Remove <diamond-data> JSON from the text and bold only the *values* in <expert-analysis>.
 */
function processChatMessage(text) {
  // 1) Remove <diamond-data> block
  let processed = text.replace(/<diamond-data>[\s\S]*?<\/diamond-data>/, "");
  
  // 2) If there's <expert-analysis>, bold only the numeric/letter values after attributes
  processed = processed.replace(/<expert-analysis>([\s\S]*?)<\/expert-analysis>/, (m, p1) => {
    return boldValues(p1);
  });
  
  return processed;
}

/**
 * Bold only the values after attribute labels (Carat, Clarity, etc.).
 */
function boldValues(text) {
  let newText = text;
  newText = newText.replace(/(Carat:\s*)([^\s,]+)/gi, '$1<strong>$2</strong>');
  newText = newText.replace(/(Clarity:\s*)([^\s,]+)/gi, '$1<strong>$2</strong>');
  newText = newText.replace(/(Color:\s*)([^\s,]+)/gi, '$1<strong>$2</strong>');
  newText = newText.replace(/(Cut:\s*)([^\s,]+)/gi, '$1<strong>$2</strong>');
  newText = newText.replace(/(Polish:\s*)([^\s,]+)/gi, '$1<strong>$2</strong>');
  newText = newText.replace(/(Symmetry:\s*)([^\s,]+)/gi, '$1<strong>$2</strong>');
  return newText;
}

/**
 * Add a chat message bubble. Bot on left, user on right, with small circular avatars.
 */
function addMessage(message, isUser = false) {
  const chatMessages = document.getElementById("chatMessages");
  
  // Create message container
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message");
  if (isUser) {
    msgDiv.classList.add("user-message");
  } else {
    msgDiv.classList.add("bot-message");
  }
  
  // Create the avatar container
  const avatarDiv = document.createElement("div");
  avatarDiv.classList.add("avatar");
  if (isUser) {
    avatarDiv.classList.add("user-avatar");
  } else {
    avatarDiv.classList.add("bot-avatar");
  }
  
  // Create avatar icon using FontAwesome classes
  const avatarIcon = document.createElement("i");
  if (isUser) {
    avatarIcon.classList.add("fas", "fa-user");
    avatarIcon.setAttribute("aria-label", "User Avatar");
  } else {
    avatarIcon.classList.add("fas", "fa-gem");
    avatarIcon.setAttribute("aria-label", "Gemma Avatar");
  }
  avatarDiv.appendChild(avatarIcon);
  
  // Create the bubble for message content
  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  if (isUser) {
    bubble.classList.add("user-bubble");
  } else {
    bubble.classList.add("bot-bubble");
  }
  
  bubble.innerHTML = processChatMessage(message);
  
  // Append in correct order based on whether message is from user or bot
  if (isUser) {
    msgDiv.appendChild(bubble);
    msgDiv.appendChild(avatarDiv);
  } else {
    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(bubble);
  }
  
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Update the search results bar text.
 */
function updateSearchResultsBar(text) {
  const searchResultsBar = document.getElementById("search-results-bar");
  if (searchResultsBar) {
    searchResultsBar.textContent = text;
  }
}

/**
 * Show the style popup.
 */
function showStylePopup() {
  document.getElementById("stylePopup").style.display = "flex";
}

/**
 * Called when user picks labgrown or natural.
 */
function selectStyle(style) {
  document.getElementById("stylePopup").style.display = "none";
  const userInput = document.getElementById("userInput");
  const sendButton = document.getElementById("sendButton");
  
  // Retrieve pending query
  const pendingQuery = localStorage.getItem("pendingQuery");
  if (pendingQuery) {
    localStorage.removeItem("pendingQuery");
    const newQuery = `${pendingQuery} ${style}`;
    addMessage(`Style preference: ${style}`, true);
    
    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: newQuery })
    })
      .then(res => res.json())
      .then(data => {
        addMessage(data.response, false);
        handleDiamondData(data.response);
      })
      .catch(err => {
        console.error("Error:", err);
        addMessage("Sorry, there was an error processing your request.", false);
      });
  }
  
  userInput.disabled = false;
  sendButton.disabled = false;
}

/**
 * Parse <diamond-data> from the chatbot response and display cards in a bot bubble.
 */
function handleDiamondData(responseText) {
  // 1) Extract the <diamond-data> block
  const diamondDataRegex = /<diamond-data>([\s\S]*?)<\/diamond-data>/;
  const match = responseText.match(diamondDataRegex);
  if (!match) {
    // No diamond-data found
    updateSearchResultsBar("");
    return;
  }

  let diamondData;
  try {
    diamondData = JSON.parse(match[1]);
  } catch (err) {
    console.error("Error parsing diamond data:", err);
    return;
  }

  // 2) Update search results bar with how many we found
  updateSearchResultsBar(`Found ${diamondData.length} Diamond${diamondData.length !== 1 ? 's' : ''} for '${lastQuery}'`);

  // 3) Build HTML for diamond cards
  // Create cards based on screen size - fewer cards for mobile
  const isMobile = window.innerWidth < 768;
  let cardsHtml = `<div class="diamond-cards-in-chat">`;
  
  for (const diamond of diamondData) {
    const priceFormatted = formatPrice(diamond.Price);
    const diamondObj = JSON.stringify(diamond).replace(/"/g, "&quot;");
    cardsHtml += `
      <div class="diamond-card-in-chat">
        <div class="diamond-header">
          <div class="diamond-title">
            <strong>${diamond.Carat}ct </strong> ${diamond.Shape}
          </div>
          <div class="diamond-price">${priceFormatted}</div>
        </div>
        <div class="diamond-specs">
          <div>Clarity:<strong>${diamond.Clarity}</strong></div>
          <div>Color:<strong>${diamond.Color}</strong></div>
          <div>Cut:<strong>${diamond.Cut}</strong></div>
          <div>Polish:<strong>${diamond.Polish}</strong></div> 
          <div>Symmetry:<strong>${diamond.Symmetry}</strong></div>
          <div>Style:<strong>${diamond.Style}</strong></div>
        </div>
        <button class="view-details-btn" onclick='openModalWithDetails(${diamondObj})'>
          View Details
        </button>
      </div>
    `;
  }
  cardsHtml += `</div>`;

  // 4) Display them in a bot message bubble
  addMessage(cardsHtml, false);
}
/**
 * Helper to format price nicely with commas, e.g. $4,795
 */
function formatPrice(value) {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0
    }).format(value);
  } catch (e) {
    return `$${value}`;
  }
}

/**
 * Open a modal with diamond details (image, looping video, PDF).
 * IMPROVED: Modal layout for better content display
 */
function openModalWithDetails(diamond) {
  const modal = document.getElementById("detailsModal");
  const modalDetails = document.getElementById("modalDetails");
  const isMobile = window.innerWidth < 768;

  // Format price with commas
  const formattedPrice = formatPrice(diamond.Price);

  // Build the modal layout with improved structure
  let modalHtml = `
    <h2>${diamond.Carat}ct ${diamond.Shape} Diamond</h2>
    <div class="modal-layout">
      <!-- Left column for details -->
      <div class="modal-left-column">
        <div class="diamond-specs-grid">
          <p>Clarity: <strong>${diamond.Clarity}</strong></p>
          <p>Color: <strong>${diamond.Color}</strong></p>
          <p>Cut: <strong>${diamond.Cut}</strong></p>
          <p>Polish: <strong>${diamond.Polish}</strong></p>
          <p>Symmetry: <strong>${diamond.Symmetry}</strong></p>
          <p>Style: <strong>${diamond.Style}</strong></p>
          <p>Lab: <strong>${diamond.Lab || 'N/A'}</strong></p>
          <p>Flourance: <strong>${diamond.Flo || 'N/A'}</strong></p>
          <p>Price: <strong>${formattedPrice}</strong></p>
        </div>
  `;

  // Add PDF link if available
  if (diamond.pdf) {
    modalHtml += `
        <div class="certificate-container">
          <a href="${diamond.pdf}" target="_blank" class="pdf-link">
            <i class="fas fa-file-pdf"></i> View Certificate
          </a>
        </div>
    `;
  }
  
  // show image right after specs for better flow
  if (diamond.image) {
    modalHtml += `
      <div class="diamond-image-container">
        <img src="${diamond.image}" alt="${diamond.Carat} Carat ${diamond.Shape}" class="diamond-image" />
      </div>
    `;
  }

  modalHtml += `</div>`; // Close details column

  // Right column for video
  modalHtml += `<div class="modal-video-column">`;
  
  // Add video
  if (diamond.video) {
    modalHtml += `
      <div class="diamond-video-container">
        <iframe 
          src="${diamond.video}"
          class="diamond-video"
          allowfullscreen
        ></iframe>
      </div>
    `;
  }

  // Add image for desktop layout
  // if (!isMobile && diamond.image) {
  //   modalHtml += `
  //     <div class="diamond-image-container">
  //       <img src="${diamond.image}" alt="${diamond.Carat} Carat ${diamond.Shape}" class="diamond-image" />
  //     </div>
  //   `;
  // }

  modalHtml += `</div></div>`; // Close media column and layout div

  // Set the HTML and display the modal
  modalDetails.innerHTML = modalHtml;
  modal.style.display = "flex";
}

/**
 * Add window resize listener to handle responsiveness dynamically
 */
window.addEventListener('resize', function() {
  // Adjust chat message container height based on window height
  const chatMessages = document.getElementById("chatMessages");
  if (chatMessages) {
    const windowHeight = window.innerHeight;
    if (windowHeight < 600) {
      chatMessages.style.maxHeight = "250px";
    } else if (windowHeight < 800) {
      chatMessages.style.maxHeight = "350px";
    } else {
      chatMessages.style.maxHeight = "450px";
    }
  }
});

/**
 * Initialize responsive settings and voice recording on page load.
 */
document.addEventListener('DOMContentLoaded', function() {
  const chatMessages = document.getElementById("chatMessages");
  if (chatMessages) {
    const windowHeight = window.innerHeight;
    if (windowHeight < 600) {
      chatMessages.style.maxHeight = "250px";
    } else if (windowHeight < 800) {
      chatMessages.style.maxHeight = "350px";
    }
  }

  // Set up voice recording functionality
  const voiceButton = document.getElementById("voiceButton");
  const userInput = document.getElementById("userInput");
  const sendButton = document.getElementById("sendButton");
  const recordingIndicator = document.getElementById("recordingIndicator");

  voiceButton.addEventListener("click", function () {
      if (confirm("Would you like to record your voice message?")) {
          startRecording();
      }
  });

  let mediaRecorder;
  let audioChunks = [];

  function startRecording() {
      if (recordingIndicator) {
          recordingIndicator.style.display = "block";
      }

      navigator.mediaDevices.getUserMedia({ audio: true })
          .then(stream => {
              mediaRecorder = new MediaRecorder(stream);
              audioChunks = [];
              mediaRecorder.start();

              mediaRecorder.addEventListener("dataavailable", event => {
                  audioChunks.push(event.data);
              });

              mediaRecorder.addEventListener("stop", () => {
                  if (recordingIndicator) {
                      recordingIndicator.style.display = "none";
                  }
                  const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
                  sendAudioForTranscription(audioBlob);
              });

              // Record for 7.5 seconds; adjust as needed
              setTimeout(() => {
                  if (mediaRecorder && mediaRecorder.state !== "inactive") {
                      mediaRecorder.stop();
                  }
              }, 7500);
          })
          .catch(err => {
              console.error("Error accessing microphone:", err);
              alert("Microphone access is required for voice input.");
          });
  }

  function sendAudioForTranscription(audioBlob) {
      let formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");

      fetch("/speech-to-text", {
          method: "POST",
          body: formData
      })
      .then(response => {
          if (!response.ok) {
              throw new Error("Transcription service error.");
          }
          return response.json();
      })
      .then(data => {
          if (data.transcript) {
              userInput.value = data.transcript;
              sendButton.click();
          } else {
              console.error("Transcript not returned:", data);
              alert("Could not transcribe your voice message. Please try again.");
          }
      })
      .catch(err => {
          console.error("Error during transcription:", err);
          alert("There was an error processing your voice input.");
      });
  }
});

/**
 * Send user message to server.
 */

function sendMessage() {
  const input = document.getElementById("userInput");
  const message = input.value.trim();
  if (!message) return;
  
  // Update the global query variable and search results bar
  lastQuery = message;
  updateSearchResultsBar(`Searching for '${message}'.....`);
  
  // Add user message to chat
  addMessage(message, true);
  input.value = "";
  
  // Hide expert recommendation when starting a new search
  hideExpertRecommendation();
  
  fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message })
  })
  .then(res => res.json())
  .then(data => {
    if (data.needs_style) {
      localStorage.setItem("pendingQuery", message);
      showStylePopup();
      return;
    }
    addMessage(data.response, false);
    handleDiamondData(data.response);
    
    // Display expert recommendation if available
    if (data.expert_recommendation) {
      showExpertRecommendation(data.expert_recommendation);
    } else {
      hideExpertRecommendation();
    }
  })
  .catch(err => {
    console.error("Error:", err);
    addMessage("Sorry, I encountered an error processing your request.", false);
    hideExpertRecommendation();
  });
}

/**
 * Show the expert recommendation section with the provided content.
 */
function showExpertRecommendation(recommendation) {
  const expertContainer = document.getElementById("expert-recommendation");
  const expertContent = document.getElementById("expert-content");
  
  // Process the recommendation content to bold values
  let processedRecommendation = processChatMessage(recommendation);
  
  // Set the content
  expertContent.innerHTML = processedRecommendation;
  
  // Show the container with a slight delay for visual effect
  setTimeout(() => {
    expertContainer.classList.remove("hidden");
    expertContainer.classList.add("visible");
  }, 300);
}

/**
 * Hide the expert recommendation section.
 */
function hideExpertRecommendation() {
  const expertContainer = document.getElementById("expert-recommendation");
  expertContainer.classList.remove("visible");
  expertContainer.classList.add("hidden");
}

/**
 * Also update the selectStyle function to handle expert recommendations
 */
function selectStyle(style) {
  document.getElementById("stylePopup").style.display = "none";
  const userInput = document.getElementById("userInput");
  const sendButton = document.getElementById("sendButton");
  
  // Retrieve pending query
  const pendingQuery = localStorage.getItem("pendingQuery");
  if (pendingQuery) {
    localStorage.removeItem("pendingQuery");
    const newQuery = `${pendingQuery} ${style}`;
    addMessage(`Style preference: ${style}`, true);
    
    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: newQuery })
    })
    .then(res => res.json())
    .then(data => {
      addMessage(data.response, false);
      handleDiamondData(data.response);
      
      // Display expert recommendation if available
      if (data.expert_recommendation) {
        showExpertRecommendation(data.expert_recommendation);
      } else {
        hideExpertRecommendation();
      }
    })
    .catch(err => {
      console.error("Error:", err);
      addMessage("Sorry, there was an error processing your request.", false);
      hideExpertRecommendation();
    });
  }
  
  userInput.disabled = false;
  sendButton.disabled = false;
}
document.getElementById("sendButton").addEventListener("click", sendMessage);
document.getElementById("userInput").addEventListener("keypress", function(event) {
  if (event.key === "Enter") {
    sendMessage();
  }
});
