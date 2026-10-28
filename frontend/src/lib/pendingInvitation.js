const PENDING_INVITE_KEY = "insightflow_pending_invite";
const LEGACY_PENDING_INVITE_KEY = ["pulse", "iq_pending_invite"].join("");

export const getPendingInvitation = () => {
  const pendingInvite = localStorage.getItem(PENDING_INVITE_KEY);
  if (pendingInvite) return pendingInvite;

  const legacyInvite = localStorage.getItem(LEGACY_PENDING_INVITE_KEY);
  if (legacyInvite) {
    localStorage.setItem(PENDING_INVITE_KEY, legacyInvite);
    localStorage.removeItem(LEGACY_PENDING_INVITE_KEY);
  }

  return legacyInvite || "";
};

export const setPendingInvitation = (token) => {
  localStorage.setItem(PENDING_INVITE_KEY, token);
  localStorage.removeItem(LEGACY_PENDING_INVITE_KEY);
};

export const clearPendingInvitation = () => {
  localStorage.removeItem(PENDING_INVITE_KEY);
  localStorage.removeItem(LEGACY_PENDING_INVITE_KEY);
};
