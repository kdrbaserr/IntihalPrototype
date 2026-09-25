const steps = [
  {
    number: "01",
    title: "Belgeni yükle",
    description: "PDF, DOCX veya TXT dosyanı güvenli biçimde sisteme ekle.",
  },
  {
    number: "02",
    title: "Analizi başlat",
    description: "Metin, yalnızca izinli kaynak havuzuyla karşılaştırılsın.",
  },
  {
    number: "03",
    title: "Eşleşmeleri incele",
    description: "Kaynakları ve skorları açıklanabilir, renkli raporda gör.",
  },
] as const;

export default function HomePage() {
  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <div className="eyebrow">Açıklanabilir · Güvenli · Ölçülebilir</div>
        <h1 id="hero-title">
          Metin benzerliğini{" "}
          <span>kanıtlarıyla incele.</span>
        </h1>
        <p className="hero-copy">
          Belgelerdeki benzer bölümleri TF-IDF ve n-gram yöntemleriyle bulur,
          sonucu kaynağı ve skoruyla birlikte gösterir.
        </p>
        <div className="hero-actions">
          <button className="primary-action" type="button" disabled>
            Belge yükleme yakında
          </button>
          <a className="secondary-action" href="#nasil-calisir">
            Nasıl çalışır?
          </a>
        </div>
      </section>

      <section className="workflow" id="nasil-calisir" aria-labelledby="workflow-title">
        <div className="section-heading">
          <span>Temel akış</span>
          <h2 id="workflow-title">Üç adımda anlaşılır sonuç</h2>
        </div>

        <div className="step-grid">
          {steps.map((step) => (
            <article className="step-card" key={step.number}>
              <span className="step-number">{step.number}</span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </article>
          ))}
        </div>
      </section>

      <aside className="notice" aria-label="Önemli bilgilendirme">
        <span className="notice-icon" aria-hidden="true">
          i
        </span>
        <div>
          <strong>Karar insanda kalır.</strong>
          <p>
            Sistem benzerlikleri görünür kılar; akademik değerlendirmeyi kullanıcı
            ve yetkili inceleyici yapar.
          </p>
        </div>
      </aside>
    </>
  );
}
