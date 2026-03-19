import streamlit as st
import shap
import matplotlib.pyplot as plt
from app2 import classify_content
from app1 import check_website

st.set_page_config(page_title="Phishing & Scam Analyzer", layout="wide", page_icon="🌐")
# Function to execute both App1 and App2 together
def run_combined_app():

    st.title("🌐 Website Scam & Phishing Analyzer")
    st.markdown("---")

    # User input
    user_input = st.text_input("🔗 Enter the full URL to analyze:")

    if user_input:
        try:
            # === MODULE 1: PHISHING DETECTION ===
            st.subheader("🔍 Module 1: Phishing Detection Analysis")
            phishing_result = classify_content(user_input)

            ml_pred = phishing_result["ml_prediction"]
            ml_conf = phishing_result["ml_confidence"]  # this is phishing probability (class=1)
            llm_pred = phishing_result["llm_prediction"]
            llm_risk = phishing_result["llm_risk_level"]

            # ✅ Convert ML probability into legitimacy confidence
            lgbm_legit_score = ml_conf

            # ✅ Convert LLM risk into legitimacy confidence
            if llm_risk == "Low":
                llm_legit_score = 0.8
            elif llm_risk == "Medium":
                llm_legit_score = 0.5
            elif llm_risk == "High":
                llm_legit_score = 0.1
            else:
                llm_legit_score = 0.5

            # 📊 Display side-by-side metrics
            col1, col2 = st.columns(2)
            col1.metric("ML (LGBM) Prediction", ml_pred, f"LegitScore={lgbm_legit_score:.3f}")
            col2.metric("LLM Prediction", f"{llm_pred} ({llm_risk})", f"LegitScore={llm_legit_score:.3f}")

            # 📝 Contextual explanations
            st.markdown("🤖 AI's Contextual Analysis**")
            if phishing_result["final_verdict"] == "phishing":
                st.write("### Phishing Indicators:")
            else:
                st.write("### Legitimate Indicators:")

            for explanation in phishing_result["ml_explanations"]:
                st.write(f"• {explanation}")

            st.markdown("### LLM Reasons:")
            for snippet in phishing_result["evidence_snippets"]:
                st.write(f"• {snippet}")

            st.markdown("---")

            # === MODULE 2: WEBSITE SIMILARITY ===
            st.subheader("🔍 Module 2: Website Similarity Analysis")
            website_similarity_result = check_website(user_input, notifier=st)

            similarity_score = None
            if isinstance(website_similarity_result, dict):
                similarity_score = website_similarity_result.get("score")

                if similarity_score is not None:
                    brand = website_similarity_result.get("brand", "Unknown")
                    st.success(f"✅ Brand matched: *{brand}*")

                    ref_image = website_similarity_result.get("reference_image", "N/A")
                    user_screenshot = website_similarity_result.get("user_screenshot", "N/A")
                    st.write(f"Comparing reference: {ref_image} ↔ {user_screenshot}")
                    st.progress(similarity_score)

                    details = website_similarity_result.get("details", {})
                    if not details:
                        details = {
                            "image": website_similarity_result.get("image_similarity", 1.0),
                            "color": website_similarity_result.get("color_similarity", 1.0),
                            "text": website_similarity_result.get("text_similarity", 0.9),
                        }

                    weights_ui = {"image": 0.5, "color": 0.4, "text": 0.1}
                    st.markdown("*Explainability Breakdown:*")
                    for k in ["image", "color", "text"]:
                        st.write(
                            f"- {k.capitalize()} contribution: {details[k]:.3f} × weight {weights_ui[k]} "
                            f"= {details[k] * weights_ui[k]:.3f}"
                        )
                else:
                    st.warning("⚠ Website similarity analysis not available.")
            else:
                st.warning("⚠ Website similarity analysis not available.")

            st.markdown("---")

            # === COMBINED FINAL ANALYSIS ===

            st.subheader("🎯 Combined Final Analysis")

            weights = {"lgbm": 0.5, "llm": 0.3, "similarity": 0.2}

            # ✅ Use legitimacy confidence for ML
            lgbm_legit_score = ml_conf

            # ✅ LLM mapping
            if phishing_result["llm_risk_level"] == "safe":
                llm_legit_score = 0.8
            elif phishing_result["llm_risk_level"] == "suspicious":
                llm_legit_score = 0.5
            elif phishing_result["llm_risk_level"] == "phishing":
                llm_legit_score = 0.1
            else:
                llm_legit_score = 0.5

            # Build score dict
            scores = {"lgbm": lgbm_legit_score, "llm": llm_legit_score}
            if similarity_score is not None:
                scores["similarity"] = similarity_score

            # Normalize weights
            active_weights = {k: v for k, v in weights.items() if k in scores}
            weight_sum = sum(active_weights.values())
            normalized_weights = {k: v / weight_sum for k, v in active_weights.items()}

            # Weighted final score
            final_legitimacy = sum(normalized_weights[k] * scores[k] for k in scores)
            final_verdict = "legitimate" if final_legitimacy >= 0.5 else "phishing"
            verdict_emoji = "🟢" if final_verdict == "legitimate" else "🔴"

            st.markdown("### Individual Component Scores (Legitimacy Confidence):")
            for k in scores:
                st.write(f"- {k.upper()}: {scores[k]:.3f} (Weight: {normalized_weights[k]*100:.1f}%)")

            st.markdown(
                f"## {verdict_emoji} FINAL COMBINED VERDICT: *{final_verdict.upper()}* "
                f"(Score = {final_legitimacy:.3f})"
            )

            if similarity_score is None:
                st.info("ℹ Final prediction based on ML + LLM only (no similarity check).")

            # Contribution chart
            st.markdown("### Contribution Breakdown")
            feature_labels = [f"{k.upper()}\n({normalized_weights[k]*100:.1f}%)" for k in scores]
            weighted_contributions = [normalized_weights[k] * scores[k] for k in scores]

            fig, ax = plt.subplots(figsize=(5, 3))  # smaller figure size
            bars = ax.bar(feature_labels, weighted_contributions, color=["#4DB6AC", "#81C784", "#E57373"])

            for bar, contribution in zip(bars, weighted_contributions):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01,
                    f"{contribution:.3f}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold"
                )

            ax.axhline(y=final_legitimacy, linestyle="--", color="red", linewidth=2,
                       label=f"Final Score = {final_legitimacy:.3f}")
            ax.axhline(y=0.5, linestyle=":", color="orange", alpha=0.7, label="Threshold = 0.5")

            ax.set_ylim(0, 1)
            ax.set_ylabel("Weighted Contribution to Legitimacy", fontsize=9)
            ax.set_title("Final Decision Contributions", fontsize=10)
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3)

            st.pyplot(fig, use_container_width=False)


        except Exception as e:
            st.error(f"❌ Error during analysis: {e}")
            st.info("Please check that your input URL is valid and all modules are configured correctly.")


def main():
    st.sidebar.title("⚙ Options")
    if st.sidebar.radio("Choose Mode", ["Combined Phishing & Similarity Check"]) == \
            "Combined Phishing & Similarity Check":
        run_combined_app()


if __name__ == "__main__":
    main()