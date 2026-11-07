import { Composer } from '../composer/Composer';

/** New-chat landing: the welcome hero and composer. */
export function HomePage() {
  return (
    <>
      <div id="messages">
        <div id="welcome-hero">
          <div className="empty-state-content">
            <div className="empty-state-greeting">
              <span className="greeting-text font-heading">Hello there</span>
              <span className="greeting-sub font-heading">How can I help you today?</span>
            </div>
          </div>
        </div>
      </div>
      <Composer />
    </>
  );
}
